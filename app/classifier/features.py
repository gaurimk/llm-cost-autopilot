"""
Feature Extraction
===================
Turns a raw prompt string into the numeric features the complexity
classifier trains and predicts on. Keeping this in one function means the
training script and the live router always compute features identically.
"""

import re

ANALYSIS_KEYWORDS = [
    "analyze", "analyse", "compare", "evaluate", "synthesize",
    "critique", "recommend", "design", "argue", "debate",
]

FORMAT_KEYWORDS = [
    "json", "table", "bullet", "csv", "yaml", "markdown", "xml",
]


def extract_features(prompt: str) -> dict:
    """Return a flat dict of numeric features for one prompt."""
    text = prompt.strip()
    lower = text.lower()
    words = lower.split()

    token_count = len(words)  # rough proxy; good enough for routing features
    analysis_keyword_count = sum(lower.count(k) for k in ANALYSIS_KEYWORDS)
    format_keyword_count = sum(lower.count(k) for k in FORMAT_KEYWORDS)

    # Number of explicit constraints: sentences containing "must", "should",
    # "only", "do not", numbered lists, etc.
    constraint_markers = ["must", "should", "only", "do not", "don't", "no more than", "exactly"]
    num_constraints = sum(lower.count(m) for m in constraint_markers)

    has_context = bool(re.search(r"(context|below|above|following|attached|provided)", lower))
    has_multi_step = bool(re.search(r"(step[s]?|first.*then|and then)", lower))
    question_marks = text.count("?")
    sentence_count = max(1, len(re.split(r"[.!?]+", text)) - 1)

    return {
        "token_count": token_count,
        "analysis_keyword_count": analysis_keyword_count,
        "format_keyword_count": format_keyword_count,
        "num_constraints": num_constraints,
        "has_context": int(has_context),
        "has_multi_step": int(has_multi_step),
        "question_marks": question_marks,
        "sentence_count": sentence_count,
    }


FEATURE_ORDER = [
    "token_count",
    "analysis_keyword_count",
    "format_keyword_count",
    "num_constraints",
    "has_context",
    "has_multi_step",
    "question_marks",
    "sentence_count",
]


def features_to_vector(features: dict) -> list:
    return [features[name] for name in FEATURE_ORDER]
