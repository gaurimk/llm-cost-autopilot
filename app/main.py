"""
LLM Cost Autopilot -- API Service
====================================
A single POST /v1/completions endpoint that behaves like a normal chat
completion API, except the caller never picks the model -- the router
does, based on the prompt's classified complexity and the current routing
config. The response includes metadata on which model was chosen and why.

Run locally with:
    uvicorn app.main:app --reload --port 8000

Full docs: see docs/DEVELOPER_GUIDE.md
"""

import asyncio
import time

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.logging_db.db import get_stats, log_request
from app.models.providers import send_request
from app.models.registry import MODEL_REGISTRY
from app.routing.router import load_routing_config, route, save_routing_config
from app.verification.verifier import verify_and_maybe_escalate

app = FastAPI(
    title="LLM Cost Autopilot",
    description="Routes requests to the cheapest model capable of handling them.",
    version="1.0.0",
)


class CompletionRequest(BaseModel):
    prompt: str = Field(..., description="The user's prompt / request text.")
    max_tokens: int | None = Field(default=1024, description="Max tokens for the response.")


class CompletionResponse(BaseModel):
    text: str
    model_selected: str
    complexity_tier: int
    routing_reason: str
    cost: float
    latency_ms: float
    request_id: int


class RoutingConfigUpdate(BaseModel):
    tier_to_model: dict[int, str] | None = None
    verifier_reference_model: str | None = None
    quality_threshold: float | None = None
    max_escalation_latency_ms: int | None = None


@app.post("/v1/completions", response_model=CompletionResponse)
async def create_completion(req: CompletionRequest):
    """
    The core endpoint. The client sends a prompt; the Autopilot decides
    which model handles it, calls that model, logs the request, and kicks
    off async quality verification in the background.
    """
    decision = route(req.prompt)
    model_config = decision["model_config"]

    try:
        response = await asyncio.to_thread(
            send_request, req.prompt, model_config, max_tokens=req.max_tokens
        )
    except Exception as exc:  # pragma: no cover - depends on live provider creds
        raise HTTPException(status_code=502, detail=f"Upstream model call failed: {exc}")

    # Reference cost = what this request would have cost on the highest
    # tier model, for the "you saved $X" dashboard metric.
    config = load_routing_config()
    reference_model = MODEL_REGISTRY[config["verifier_reference_model"]]
    reference_cost = reference_model.estimate_cost(response.input_tokens, response.output_tokens)

    request_id = log_request(
        prompt=req.prompt,
        complexity_tier=decision["tier"],
        routed_model=decision["model_name"],
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        cost=response.cost,
        reference_cost=reference_cost,
        latency_ms=response.latency_ms,
    )

    # Fire-and-forget: verify quality in the background without blocking
    # the response the user is waiting on.
    asyncio.create_task(verify_and_maybe_escalate(request_id, req.prompt, response))

    return CompletionResponse(
        text=response.text,
        model_selected=decision["model_name"],
        complexity_tier=decision["tier"],
        routing_reason=decision["reason"],
        cost=response.cost,
        latency_ms=response.latency_ms,
        request_id=request_id,
    )


@app.get("/v1/models")
def list_models():
    """List every model in the registry and its pricing."""
    return {
        name: {
            "provider": cfg.provider.value,
            "model_id": cfg.model_id,
            "cost_per_1k_input": cfg.cost_per_1k_input,
            "cost_per_1k_output": cfg.cost_per_1k_output,
            "avg_latency_ms": cfg.avg_latency_ms,
            "quality_tier": cfg.quality_tier.value,
        }
        for name, cfg in MODEL_REGISTRY.items()
    }


@app.get("/v1/stats")
def stats():
    """Cost savings summary -- powers the dashboard's headline numbers."""
    return get_stats()


@app.get("/v1/routing-config")
def get_routing_config():
    return load_routing_config()


@app.put("/v1/routing-config")
def update_routing_config(update: RoutingConfigUpdate):
    """Update tier-to-model mappings (or other routing settings) without redeploying."""
    config = load_routing_config()
    updates = update.model_dump(exclude_none=True)

    if "tier_to_model" in updates:
        for name in updates["tier_to_model"].values():
            if name not in MODEL_REGISTRY:
                raise HTTPException(status_code=400, detail=f"Unknown model '{name}'")
        config["tier_to_model"] = {int(k): v for k, v in updates["tier_to_model"].items()}

    for key in ("verifier_reference_model", "quality_threshold", "max_escalation_latency_ms"):
        if key in updates:
            config[key] = updates[key]

    save_routing_config(config)
    return config


@app.get("/healthz")
def health():
    return {"status": "ok"}
