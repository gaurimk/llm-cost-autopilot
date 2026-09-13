# Developer Guide

This guide covers setup, how each phase of the build was implemented, how
to test it, and how to extend it. It assumes basic Python familiarity but
explains framework-specific choices (FastAPI, scikit-learn, SQLite) as
they come up.

## Setup

```bash
git clone https://github.com/gaurimk/llm-cost-autopilot
cd llm-cost-autopilot
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in OPENAI_API_KEY / ANTHROPIC_API_KEY
```

Everything except live provider calls (i.e. `tests/test_basic.py`, the
classifier, the router, and cost math) works with **no API keys at all**.
You only need real keys to actually call OpenAI/Anthropic, or a running
Ollama instance for the local model.

## Phase-by-phase implementation notes

### Phase 1 — Unified Model Interface (`app/models/`)

- `registry.py` defines a frozen `ModelConfig` dataclass and a
  `MODEL_REGISTRY` dict. Adding a new model means adding one entry here —
  no other file needs to change.
- `providers.py` exposes one function, `send_request(prompt, model_config)`,
  that dispatches to provider-specific private functions
  (`_call_openai`, `_call_anthropic`, `_call_ollama`) and normalizes all
  three into one `Response` dataclass (text, tokens, latency, cost,
  model_id).
- **To test every provider against the same prompts** (build guide step
  3), you can adapt `tests/test_basic.py` or write a short script that
  loops `MODEL_REGISTRY` and calls `send_request` for a fixed prompt list,
  logging cost/latency per model. This was intentionally left as an
  exercise rather than hardcoded here, since it requires live API keys to
  run meaningfully.

### Phase 2 — Complexity Classifier (`app/classifier/`)

- `features.py` extracts 8 numeric features per prompt (token count,
  keyword counts, constraint markers, etc.) — see the file for the exact
  list and rationale.
- `data/generate_seed_dataset.py` generates a **template-based seed
  dataset** of 210 labeled prompts (70 per tier). This is explicitly a
  bootstrap, not a substitute for 200+ hand-labeled real examples — see
  the honesty note at the top of that file and in the README.
- `train.py` trains a `scikit-learn` `LogisticRegression` model, holds out
  25% for evaluation, and warns if accuracy falls below 80%. As shipped,
  it measures **81.13% held-out accuracy** — right at the V1 bar the
  build guide sets, using the templated seed set. Expect real accuracy to
  be lower until you replace the seed set with real labeled traffic.
- `classifier.py` is the inference wrapper the router calls. It falls
  back to a simple heuristic if no trained model file exists, so the API
  doesn't hard-crash if you skip training.

**To retrain:**
```bash
python data/generate_seed_dataset.py   # or supply your own training_prompts.csv
PYTHONPATH=. python -m app.classifier.train
```

### Phase 3 — Async Quality Verification (`app/verification/`)

- `verifier.py`'s `verify_and_maybe_escalate()` is designed to be
  scheduled with `asyncio.create_task()` (see its call site in
  `app/main.py`) so it runs *after* the response is already sent to the
  user.
- It uses the configured reference model both to generate a "gold" answer
  and to score the cheap model's answer 1–5 (LLM-as-judge). This is a
  simplification: the build guide's Phase 3 step 1 calls for
  use-case-specific quality definitions (exact field match for
  extraction, LLM-judge for summarization, label match for
  classification). As shipped, one general judge prompt covers all cases;
  see `ARCHITECTURE.md`'s "known limitations" for how you'd split this out
  per use case.
- Escalation events update the same SQLite row rather than creating a new
  one, via `update_quality_score()`.
- **Not implemented**: the weekly classifier retraining loop from Phase 3
  step 4. The data needed for it (escalation flag + tier + prompt hash) is
  already in the `requests` table — you'd add a scheduled job that pulls
  rows where `escalated = 1`, reconstructs labeled examples (you'd need to
  store enough of the original prompt to relabel it, which the current
  hash-only storage intentionally does not do — see the privacy note in
  `db.py`), and appends them to the training set before re-running
  `train.py`.

### Phase 4 — Logging and Dashboard (`app/logging_db/`, `app/dashboard/`)

- `db.py` uses plain `sqlite3` (no ORM) with one `requests` table. Prompts
  are stored as a SHA-256 hash truncated to 16 hex characters, not raw
  text — see the privacy note in the file's docstring.
- `get_stats()` computes the aggregate numbers the API's `/v1/stats`
  endpoint and the dashboard both use, so they never drift out of sync.
- `streamlit_app.py` reads directly from the SQLite file (no API
  round-trip) and shows: headline cost-saved %, cost-over-time chart,
  routing distribution, quality score distribution, and escalation rate
  over time.

### Phase 5 — API (`app/main.py`)

- Single `POST /v1/completions` endpoint. The request body only contains
  `prompt` (and optional `max_tokens`) — there's no `model` field, by
  design.
- `GET /v1/models`, `GET /v1/stats`, `GET`/`PUT /v1/routing-config` are
  all implemented per the build guide's Phase 5 step 2.
- Routing config updates via `PUT /v1/routing-config` are validated
  against the model registry (you can't route a tier to a model that
  doesn't exist) and persisted straight to the YAML file, so they survive
  a restart.

### Phase 6 — Load Test & Portfolio Polish (`scripts/load_test.py`)

- Sends a configurable number of diverse prompts (drawn from the same
  template generator as the training data, for variety) through the
  running API concurrently, then prints the final `/v1/stats` summary.
- Run it, screenshot the Streamlit dashboard, and pull the `/v1/stats`
  JSON — those are your portfolio artifacts, per the build guide.

```bash
python scripts/load_test.py --n 500 --base-url http://localhost:8000
```

## Running tests

```bash
PYTHONPATH=. pytest tests/ -v
```

All 7 tests pass without any API keys — they test feature extraction,
classification, routing decisions, and cost math, none of which require a
live model call.

## Extending the system

- **Add a model:** add one entry to `MODEL_REGISTRY` in
  `app/models/registry.py`, then reference its key in
  `routing_config.yaml`.
- **Add a provider:** add a `_call_<provider>` function in
  `providers.py` and a branch in `send_request()`.
- **Change routing logic:** edit `routing_config.yaml` directly, or
  `PUT /v1/routing-config` at runtime.
- **Improve the classifier:** add real labeled examples to
  `data/training_prompts.csv` (same two-column `prompt,tier` format) and
  re-run `train.py`.
