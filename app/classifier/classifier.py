"""
Complexity Classifier (inference wrapper)
===========================================
Loads the trained model saved by train.py and exposes a single
`classify(prompt) -> int` function (returns 1, 2, or 3) used by the router.

Falls back to a simple heuristic if no trained model file exists yet, so the
API doesn't hard-fail if someone hasn't run training first.
"""

from pathlib import Path

import numpy as np

from app.classifier.features import extract_features, features_to_vector

MODEL_PATH = Path(__file__).resolve().parent / "model.joblib"

_model = None
_model_load_attempted = False


def _load_model():
    global _model, _model_load_attempted
    if _model_load_attempted:
        return _model
    _model_load_attempted = True
    if MODEL_PATH.exists():
        import joblib
        _model = joblib.load(MODEL_PATH)
    return _model


def _heuristic_classify(features: dict) -> int:
    """Fallback used only if no trained model is present."""
    if features["analysis_keyword_count"] > 0 or features["has_multi_step"]:
        return 3
    if features["format_keyword_count"] > 0 or features["token_count"] > 40:
        return 2
    return 1


def classify(prompt: str) -> int:
    features = extract_features(prompt)
    model = _load_model()
    if model is None:
        return _heuristic_classify(features)
    vector = np.array(features_to_vector(features)).reshape(1, -1)
    return int(model.predict(vector)[0])
