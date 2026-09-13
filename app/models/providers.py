"""
Unified Model Interface
========================
A single `send_request(prompt, model_config)` function that hides the
differences between OpenAI, Anthropic, and local Ollama calls behind one
interface. Every call returns a standardized `Response` object regardless
of which provider handled it, so the rest of the system (classifier,
router, verifier, dashboard) never needs to know which provider is behind
a given model name.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass

from app.models.registry import ModelConfig, Provider

# Providers are imported lazily inside the functions that need them so this
# module can be imported (e.g. for tests) even if a given SDK isn't installed.


@dataclass
class Response:
    text: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    cost: float
    model_id: str
    provider: str
    raw: dict | None = None


def send_request(prompt: str, model_config: ModelConfig, **kwargs) -> Response:
    """
    Send `prompt` to the model described by `model_config` and return a
    standardized Response. This is the ONLY function the rest of the
    codebase should call to talk to a model -- add new providers here,
    not scattered throughout the app.
    """
    start = time.perf_counter()

    if model_config.provider == Provider.OPENAI:
        text, in_tok, out_tok, raw = _call_openai(prompt, model_config, **kwargs)
    elif model_config.provider == Provider.ANTHROPIC:
        text, in_tok, out_tok, raw = _call_anthropic(prompt, model_config, **kwargs)
    elif model_config.provider == Provider.OLLAMA:
        text, in_tok, out_tok, raw = _call_ollama(prompt, model_config, **kwargs)
    else:
        raise ValueError(f"Unsupported provider: {model_config.provider}")

    latency_ms = (time.perf_counter() - start) * 1000
    cost = model_config.estimate_cost(in_tok, out_tok)

    return Response(
        text=text,
        input_tokens=in_tok,
        output_tokens=out_tok,
        latency_ms=latency_ms,
        cost=cost,
        model_id=model_config.model_id,
        provider=model_config.provider.value,
        raw=raw,
    )


# ---------------------------------------------------------------------------
# Provider-specific implementations. Each returns (text, input_tokens,
# output_tokens, raw_response_dict).
# ---------------------------------------------------------------------------

def _call_openai(prompt: str, cfg: ModelConfig, **kwargs):
    from openai import OpenAI

    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    resp = client.chat.completions.create(
        model=cfg.model_id,
        messages=[{"role": "user", "content": prompt}],
        **kwargs,
    )
    text = resp.choices[0].message.content
    usage = resp.usage
    return text, usage.prompt_tokens, usage.completion_tokens, resp.model_dump()


def _call_anthropic(prompt: str, cfg: ModelConfig, **kwargs):
    import anthropic

    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    resp = client.messages.create(
        model=cfg.model_id,
        max_tokens=kwargs.pop("max_tokens", 1024),
        messages=[{"role": "user", "content": prompt}],
        **kwargs,
    )
    text = "".join(block.text for block in resp.content if block.type == "text")
    return text, resp.usage.input_tokens, resp.usage.output_tokens, resp.model_dump()


def _call_ollama(prompt: str, cfg: ModelConfig, **kwargs):
    import requests

    base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    resp = requests.post(
        f"{base_url}/api/generate",
        json={"model": cfg.model_id, "prompt": prompt, "stream": False},
        timeout=kwargs.pop("timeout", 120),
    )
    resp.raise_for_status()
    data = resp.json()
    text = data.get("response", "")
    # Ollama reports token counts; fall back to rough estimate if missing.
    in_tok = data.get("prompt_eval_count") or max(1, len(prompt) // 4)
    out_tok = data.get("eval_count") or max(1, len(text) // 4)
    return text, in_tok, out_tok, data
