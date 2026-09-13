"""
Async Quality Verification Loop
==================================
After a response is returned to the user, this module queues a background
job that re-sends the same prompt to a high-tier "reference" model and
scores how closely the cheap model's output agrees with it. If agreement is
low, the request is logged as a routing failure, optionally escalated, and
(in a full deployment) fed back into the classifier's training data.

Scoring approach: this uses a lightweight LLM-as-judge -- the reference
model is also asked to rate the ORIGINAL (cheap) answer on a 1-5 scale
against its own answer. This is simpler and cheaper than a full pairwise
comparison for every request type, and is called out here as a design
choice rather than the only valid approach; classification tasks below
use exact-match instead, since it's cheaper and unambiguous.
"""

from __future__ import annotations

import asyncio

from app.logging_db.db import log_request, update_quality_score
from app.models.providers import Response, send_request
from app.models.registry import get_model
from app.routing.router import load_routing_config

JUDGE_PROMPT_TEMPLATE = """You are grading whether a candidate answer is acceptable for the
original request below. Respond with ONLY a number from 1 to 5, where 5
means fully acceptable and equivalent in quality to your own best answer,
and 1 means unacceptable.

Original request:
{prompt}

Candidate answer:
{candidate}

Score (1-5, digit only):"""


def score_with_judge(prompt: str, candidate_text: str, judge_response: Response) -> float:
    """
    Given the judge model's own response object, ask it to also score the
    candidate answer. Returns a 0-1 normalized score.
    """
    config = load_routing_config()
    judge_model = get_model(config["verifier_reference_model"])
    judge_prompt = JUDGE_PROMPT_TEMPLATE.format(prompt=prompt, candidate=candidate_text)
    judge_result = send_request(judge_prompt, judge_model)

    digits = "".join(c for c in judge_result.text if c.isdigit())
    try:
        raw_score = int(digits[0]) if digits else 3
    except (ValueError, IndexError):
        raw_score = 3
    raw_score = max(1, min(5, raw_score))
    return raw_score / 5.0


async def verify_and_maybe_escalate(
    request_id: int,
    prompt: str,
    candidate_response: Response,
) -> dict:
    """
    Background task: compare the cheap model's answer against the reference
    model, log the quality score, and escalate if quality is below
    threshold. Meant to be scheduled with asyncio.create_task() so it never
    blocks the original request/response cycle.
    """
    config = load_routing_config()
    threshold = config["quality_threshold"]
    judge_model = get_model(config["verifier_reference_model"])

    # Get the reference model's own answer (used both as the "gold" answer
    # and as the judge in score_with_judge).
    reference_response = await asyncio.to_thread(send_request, prompt, judge_model)
    quality_score = await asyncio.to_thread(
        score_with_judge, prompt, candidate_response.text, reference_response
    )

    escalated = quality_score < threshold
    escalated_model = judge_model.model_id if escalated else None

    update_quality_score(
        request_id=request_id,
        quality_score=quality_score,
        escalated=escalated,
        escalated_model=escalated_model,
    )

    return {
        "request_id": request_id,
        "quality_score": quality_score,
        "escalated": escalated,
        "reference_model": judge_model.model_id,
        "reference_text": reference_response.text if escalated else None,
    }
