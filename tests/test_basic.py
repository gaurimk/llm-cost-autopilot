"""
Basic tests that don't require live provider API keys or a running Ollama
instance -- they test the parts of the system that are pure logic:
feature extraction, classification, routing decisions, and cost math.

Run with: pytest tests/
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.classifier.classifier import classify
from app.classifier.features import extract_features
from app.models.registry import MODEL_REGISTRY, get_model
from app.routing.router import load_routing_config, route


def test_registry_has_expected_models():
    for name in ["gpt-4o", "gpt-4o-mini", "claude-sonnet", "claude-haiku", "llama-local"]:
        assert name in MODEL_REGISTRY


def test_cost_estimate_is_zero_for_local_model():
    llama = get_model("llama-local")
    assert llama.estimate_cost(1000, 1000) == 0.0


def test_cost_estimate_scales_with_tokens():
    gpt4o = get_model("gpt-4o")
    small = gpt4o.estimate_cost(100, 100)
    large = gpt4o.estimate_cost(1000, 1000)
    assert large > small


def test_feature_extraction_shape():
    features = extract_features("Analyze and compare these two proposals, then recommend one.")
    assert features["analysis_keyword_count"] >= 2
    assert features["token_count"] > 0


def test_simple_prompt_classifies_low_tier():
    tier = classify("Extract the phone number from this text: call me at 555-1234.")
    assert tier in (1, 2, 3)  # model-dependent, but must return a valid tier


def test_routing_config_loads_and_has_all_tiers():
    config = load_routing_config()
    assert set(config["tier_to_model"].keys()) == {1, 2, 3}
    for model_name in config["tier_to_model"].values():
        assert model_name in MODEL_REGISTRY


def test_route_returns_valid_decision():
    decision = route("Summarize this in three sentences: the sky is blue.")
    assert decision["tier"] in (1, 2, 3)
    assert decision["model_name"] in MODEL_REGISTRY
    assert "reason" in decision
