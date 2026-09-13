"""
Router
=======
The decision-making core of the Autopilot: given a prompt, decide which
model should handle it, based on the complexity classifier's tier
prediction and the configurable tier -> model routing map.

This module intentionally does NOT call the LLM itself -- that's
`app.models.providers.send_request`. Keeping routing decisions separate
from execution makes both easier to test.
"""

from pathlib import Path

import yaml

from app.classifier.classifier import classify
from app.models.registry import get_model

CONFIG_PATH = Path(__file__).resolve().parent / "routing_config.yaml"

_config_cache: dict | None = None


def load_routing_config(force_reload: bool = False) -> dict:
    global _config_cache
    if _config_cache is None or force_reload:
        with open(CONFIG_PATH) as f:
            _config_cache = yaml.safe_load(f)
    return _config_cache


def save_routing_config(config: dict) -> None:
    """Persist an updated routing config to disk (used by PUT /v1/routing-config)."""
    global _config_cache
    with open(CONFIG_PATH, "w") as f:
        yaml.safe_dump(config, f, sort_keys=False)
    _config_cache = config


def route(prompt: str) -> dict:
    """
    Decide which model should handle `prompt`.

    Returns a dict with the routing decision and the reasoning behind it,
    so the API can return "which model was selected and why" as required
    by Phase 5.
    """
    config = load_routing_config()
    tier = classify(prompt)
    model_name = config["tier_to_model"][tier]
    model_config = get_model(model_name)

    return {
        "tier": tier,
        "model_name": model_name,
        "model_config": model_config,
        "reason": (
            f"Prompt classified as complexity tier {tier}; "
            f"routing config maps tier {tier} to '{model_name}'."
        ),
    }
