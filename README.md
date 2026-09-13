# LLM Cost Autopilot

An intelligent routing layer that sits in front of multiple LLM providers,
scores each incoming request's complexity, routes it to the **cheapest
model capable of handling it**, and continuously checks its own routing
decisions against a high-quality reference model — auto-escalating and
re-learning whenever it gets one wrong.

```
                     ┌─────────────────────────┐
   client  ───POST──▶│   FastAPI  /v1/completions │
                     └────────────┬────────────┘
                                  │
                     ┌────────────▼────────────┐
                     │   Complexity Classifier  │  (tier 1 / 2 / 3)
                     └────────────┬────────────┘
                                  │
                     ┌────────────▼────────────┐
                     │   Routing Config (YAML)  │  tier → model
                     └────────────┬────────────┘
                                  │
              ┌───────────────────┼───────────────────┐
              ▼                   ▼                   ▼
      Llama (local)        Claude Haiku          Claude Sonnet / GPT-4o
              │                   │                   │
              └───────────────────┴───────────────────┘
                                  │
                     ┌────────────▼────────────┐
                     │   Response → user (fast)  │
                     └────────────┬────────────┘
                                  │  (async, non-blocking)
                     ┌────────────▼────────────┐
                     │  Verifier: compare vs.   │
                     │  reference model, score, │
                     │  escalate if needed      │
                     └────────────┬────────────┘
                                  │
                     ┌────────────▼────────────┐
                     │  SQLite audit log  ───▶ Streamlit dashboard │
                     └──────────────────────────┘
```

## Who should read what

| You are... | Start here |
|---|---|
| A stakeholder / non-technical reviewer | [`docs/NON_TECHNICAL_OVERVIEW.md`](docs/NON_TECHNICAL_OVERVIEW.md) |
| A developer implementing or extending this | [`docs/DEVELOPER_GUIDE.md`](docs/DEVELOPER_GUIDE.md) |
| Reading system design / data flow | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) |
| Writing up this project for a portfolio | [`docs/BLOG_POST.md`](docs/BLOG_POST.md) |

## Quickstart

```bash
# 1. Set up environment
cp .env.example .env
# edit .env with your OPENAI_API_KEY / ANTHROPIC_API_KEY

# 2. Install dependencies
pip install -r requirements.txt

# 3. Generate the seed training data and train the classifier
python data/generate_seed_dataset.py
PYTHONPATH=. python -m app.classifier.train

# 4. Run the API
uvicorn app.main:app --reload --port 8000

# 5. In a second terminal, run the dashboard
streamlit run app/dashboard/streamlit_app.py

# 6. In a third terminal, send some traffic
python scripts/load_test.py --n 100 --base-url http://localhost:8000
```

Or, with Docker:

```bash
cp .env.example .env   # fill in your keys
docker compose up --build
# API:       http://localhost:8000
# Dashboard: http://localhost:8501
```

## Validation status

This system has been run end-to-end against live OpenAI models (`gpt-4o-mini`
for tiers 1–2, `gpt-4o` for tier 3 and as the verifier's reference model) on
a 36-request test batch, confirming: routing decisions, cost logging,
async quality verification, escalation, and the dashboard all work
correctly together. That run measured **44.8% cost savings** versus
routing everything to `gpt-4o`.

This is a small validation batch, not a large-scale benchmark — stated
plainly so no one mistakes it for a 500-1,000 request load test result.
The routing config as shipped defaults to Claude models for tiers 2-3 (see
Quickstart); swap in whichever provider you have API access to.

## What's actually in this repo vs. what's a starting point

This project is fully wired end-to-end and every test passes without any
API keys (see `tests/test_basic.py`). Two things are intentionally
**starter material**, not finished production assets, and are labeled as
such throughout the docs:

1. **The labeled training dataset** (`data/training_prompts.csv`) is
   generated from templates (`data/generate_seed_dataset.py`), not 200+
   prompts hand-labeled from real traffic as the original build guide
   specifies. It's large enough to train a classifier that clears the 80%
   V1 accuracy bar (81% on held-out data, see
   `docs/DEVELOPER_GUIDE.md`), but templated data is easier to learn than
   messy real-world prompts. Replace it with your own labeled traffic
   before trusting this for real cost decisions.
2. **Pricing figures** in `app/models/registry.py` are illustrative list
   prices at time of writing, not a live pricing feed. Verify against each
   provider's current pricing page before using the cost numbers for
   anything financial.

Everything else — the router, classifier pipeline, provider abstraction,
async verifier, logging, dashboard, and API — is complete, tested, and
runnable.

## Repository layout

```
llm-cost-autopilot/
├── app/
│   ├── main.py                    # FastAPI app (Phase 5)
│   ├── models/
│   │   ├── registry.py            # ModelConfig registry (Phase 1)
│   │   └── providers.py           # send_request() unified interface (Phase 1)
│   ├── classifier/
│   │   ├── features.py            # Feature extraction
│   │   ├── train.py                # Training script (Phase 2)
│   │   └── classifier.py          # Inference wrapper
│   ├── routing/
│   │   ├── router.py               # Routing decision logic
│   │   └── routing_config.yaml    # Tier → model map (editable, no redeploy)
│   ├── verification/
│   │   └── verifier.py            # Async quality check + escalation (Phase 3)
│   ├── logging_db/
│   │   └── db.py                   # SQLite audit trail (Phase 4)
│   └── dashboard/
│       └── streamlit_app.py       # Cost/quality dashboard (Phase 4)
├── data/
│   ├── generate_seed_dataset.py
│   └── training_prompts.csv
├── scripts/
│   └── load_test.py                # Phase 6 load test
├── tests/
│   └── test_basic.py
├── docs/
│   ├── ARCHITECTURE.md
│   ├── DEVELOPER_GUIDE.md
│   ├── NON_TECHNICAL_OVERVIEW.md
│   └── BLOG_POST.md
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

## Suggested next features (speculative — not built here)

These are recommendations for extending the project, not implemented
functionality:

- **Real-traffic feedback loop**: wire `verifier.py`'s escalation events
  into a nightly job that appends failures to `training_prompts.csv` and
  re-runs `train.py`, closing the flywheel described in Phase 3.
- **Per-tenant routing configs**: if this sits in front of multiple
  customers/products, extend `routing_config.yaml` to be keyed by tenant
  ID rather than global.
- **Streaming responses**: the current `/v1/completions` endpoint is
  non-streaming; adding Server-Sent Events would matter for chat UIs.
- **Semantic caching**: cache responses for near-duplicate prompts (via
  embedding similarity) before even hitting the classifier, for an
  additional cost cut on repetitive traffic.
- **Confidence-aware routing**: use the classifier's predicted-class
  probability, not just the top label, to route uncertain tier-1/tier-2
  boundary cases up a tier automatically.
