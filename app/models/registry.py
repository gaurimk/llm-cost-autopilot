"""
Model Registry
===============
Defines every model the router is allowed to choose between, along with the
data needed to make a cost-aware routing decision: price per token, expected
latency, and a coarse "quality tier" (high/medium/low).

Prices are illustrative list prices (USD per 1,000 tokens) as of the project
build date. Real deployments should pull these from each provider's pricing
page periodically -- see docs/DEVELOPER_GUIDE.md for a note on keeping this
file current.
"""

from dataclasses import dataclass
from enum import Enum


class QualityTier(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Provider(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"  # local, self-hosted


@dataclass(frozen=True)
class ModelConfig:
    provider: Provider
    model_id: str
    cost_per_1k_input: float   # USD
    cost_per_1k_output: float  # USD
    avg_latency_ms: int
    quality_tier: QualityTier

    @property
    def is_local(self) -> bool:
        return self.provider == Provider.OLLAMA

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        return (
            (input_tokens / 1000) * self.cost_per_1k_input
            + (output_tokens / 1000) * self.cost_per_1k_output
        )


# ---------------------------------------------------------------------------
# The registry. Add/remove rows here to change what the router can pick from.
# No other code needs to change when you add a model.
# ---------------------------------------------------------------------------
MODEL_REGISTRY: dict[str, ModelConfig] = {
    "gpt-4o": ModelConfig(
        provider=Provider.OPENAI,
        model_id="gpt-4o",
        cost_per_1k_input=0.0025,
        cost_per_1k_output=0.0100,
        avg_latency_ms=1800,
        quality_tier=QualityTier.HIGH,
    ),
    "gpt-4o-mini": ModelConfig(
        provider=Provider.OPENAI,
        model_id="gpt-4o-mini",
        cost_per_1k_input=0.00015,
        cost_per_1k_output=0.0006,
        avg_latency_ms=900,
        quality_tier=QualityTier.MEDIUM,
    ),
    "claude-sonnet": ModelConfig(
        provider=Provider.ANTHROPIC,
        model_id="claude-sonnet-4-6",
        cost_per_1k_input=0.003,
        cost_per_1k_output=0.015,
        avg_latency_ms=1600,
        quality_tier=QualityTier.HIGH,
    ),
    "claude-haiku": ModelConfig(
        provider=Provider.ANTHROPIC,
        model_id="claude-haiku-4-5-20251001",
        cost_per_1k_input=0.00025,
        cost_per_1k_output=0.00125,
        avg_latency_ms=700,
        quality_tier=QualityTier.MEDIUM,
    ),
    "llama-local": ModelConfig(
        provider=Provider.OLLAMA,
        model_id="llama3.1:8b",
        cost_per_1k_input=0.0,   # self-hosted: no per-token API cost
        cost_per_1k_output=0.0,
        avg_latency_ms=1200,     # varies a lot by hardware
        quality_tier=QualityTier.LOW,
    ),
}


def get_model(name: str) -> ModelConfig:
    if name not in MODEL_REGISTRY:
        raise KeyError(f"Unknown model '{name}'. Known models: {list(MODEL_REGISTRY)}")
    return MODEL_REGISTRY[name]
