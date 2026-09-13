"""
Logging Database
==================
Every request gets one row: timestamp, prompt hash (not the raw prompt --
see the privacy note below), complexity tier, routed model, cost, latency,
quality score from the verifier, and whether it was escalated. This is the
audit trail the cost dashboard and case study numbers are built from.

PRIVACY NOTE: we store a hash of the prompt, not the prompt text itself, so
the audit database doesn't become a second copy of potentially sensitive
user content. If you need full prompt replay for debugging, log prompts to
a separate, access-controlled store with its own retention policy -- don't
just widen this table.
"""

import hashlib
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "autopilot.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL NOT NULL,
    prompt_hash TEXT NOT NULL,
    complexity_tier INTEGER NOT NULL,
    routed_model TEXT NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cost REAL NOT NULL,
    reference_cost REAL NOT NULL,
    latency_ms REAL NOT NULL,
    quality_score REAL,
    escalated INTEGER NOT NULL DEFAULT 0,
    escalated_model TEXT
);
"""


@contextmanager
def get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.execute(SCHEMA)
        conn.commit()


def hash_prompt(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]


def log_request(
    prompt: str,
    complexity_tier: int,
    routed_model: str,
    input_tokens: int,
    output_tokens: int,
    cost: float,
    reference_cost: float,
    latency_ms: float,
    quality_score: float | None = None,
    escalated: bool = False,
    escalated_model: str | None = None,
) -> int:
    init_db()
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO requests (
                timestamp, prompt_hash, complexity_tier, routed_model,
                input_tokens, output_tokens, cost, reference_cost, latency_ms,
                quality_score, escalated, escalated_model
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                time.time(),
                hash_prompt(prompt),
                complexity_tier,
                routed_model,
                input_tokens,
                output_tokens,
                cost,
                reference_cost,
                latency_ms,
                quality_score,
                int(escalated),
                escalated_model,
            ),
        )
        conn.commit()
        return cur.lastrowid


def update_quality_score(request_id: int, quality_score: float, escalated: bool, escalated_model: str | None):
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE requests
            SET quality_score = ?, escalated = ?, escalated_model = ?
            WHERE id = ?
            """,
            (quality_score, int(escalated), escalated_model, request_id),
        )
        conn.commit()


def get_stats() -> dict:
    init_db()
    with get_conn() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM requests").fetchall()

    if not rows:
        return {
            "total_requests": 0,
            "total_cost": 0.0,
            "reference_cost": 0.0,
            "savings_pct": 0.0,
            "escalation_rate": 0.0,
            "avg_quality_score": None,
            "model_distribution": {},
        }

    total_cost = sum(r["cost"] for r in rows)
    reference_cost = sum(r["reference_cost"] for r in rows)
    savings_pct = (
        ((reference_cost - total_cost) / reference_cost) * 100 if reference_cost > 0 else 0.0
    )
    escalations = sum(r["escalated"] for r in rows)
    quality_scores = [r["quality_score"] for r in rows if r["quality_score"] is not None]

    distribution: dict[str, int] = {}
    for r in rows:
        distribution[r["routed_model"]] = distribution.get(r["routed_model"], 0) + 1

    return {
        "total_requests": len(rows),
        "total_cost": round(total_cost, 6),
        "reference_cost": round(reference_cost, 6),
        "savings_pct": round(savings_pct, 2),
        "escalation_rate": round(escalations / len(rows) * 100, 2),
        "avg_quality_score": (
            round(sum(quality_scores) / len(quality_scores), 3) if quality_scores else None
        ),
        "model_distribution": distribution,
    }
