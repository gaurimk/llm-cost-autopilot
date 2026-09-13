# Architecture

This document explains how a request moves through the system, what each
component is responsible for, and why it's built this way. It assumes you've
read the README quickstart but doesn't assume prior familiarity with any
specific piece (FastAPI, scikit-learn, etc.) — each is explained where it's
introduced.

## 1. The request lifecycle

1. A client sends `POST /v1/completions` with a `prompt` (see
   `app/main.py`). The client does **not** specify a model — that's the
   entire point of the router.
2. **Classification** (`app/classifier/classifier.py`): the prompt is
   converted into a small set of numeric features (word count, presence of
   words like "analyze" or "compare", number of constraints, etc. — see
   `app/classifier/features.py`) and a trained model predicts a
   **complexity tier**: 1 (simple), 2 (moderate), or 3 (complex).
3. **Routing** (`app/routing/router.py`): the tier is looked up in
   `routing_config.yaml`, a plain YAML file that maps each tier to a model
   name. This file can be edited directly, or updated live via
   `PUT /v1/routing-config`, without redeploying any code.
4. **Execution** (`app/models/providers.py`): the chosen model is called
   through `send_request()`, a single function that hides the differences
   between OpenAI's, Anthropic's, and a local Ollama's APIs. Every call —
   regardless of provider — returns the same `Response` shape: text,
   token counts, latency, and cost.
5. **Logging** (`app/logging_db/db.py`): the request is written to a
   SQLite table with everything needed for cost reporting and auditing:
   which tier it was, which model handled it, tokens used, cost, latency.
   The prompt itself is stored as a hash, not raw text, to avoid the audit
   log becoming an unmanaged copy of potentially sensitive content.
6. **Response returned to the user** — at this point the client already
   has their answer. Steps 7–8 happen *after* this, in the background.
7. **Async verification** (`app/verification/verifier.py`): a background
   task re-sends the same prompt to a high-tier "reference" model (GPT-4o
   by default) and uses that same reference model as an LLM-as-judge to
   score the cheap model's original answer from 1–5. This never delays the
   response the user already received.
8. **Escalation**: if the score falls below a configurable threshold, the
   request is flagged as a routing failure. In a full production version
   of this system, failures like this would be fed back into the training
   set so the classifier improves over time — the hook for that is
   described in the README's "suggested next features," since building the
   automated retraining job itself was out of scope here.

## 2. Why these design choices

**Why separate "classify" from "route"?**
The classifier answers "how hard is this?" The router answers "given how
hard it is, and today's model prices, which model should handle it?"
Separating them means you can update model pricing or swap which model
handles tier 2 (e.g., because a provider raised prices) by editing one
YAML file — the classifier doesn't need to be retrained just because
prices changed.

**Why a unified `send_request()` instead of calling each provider's SDK
directly everywhere?**
Every other part of the system (classifier's routing decision, the
verifier, the dashboard) only ever needs to know "which model, what did it
cost, what did it say." If OpenAI or Anthropic change their SDK, only
`app/models/providers.py` needs to change.

**Why hash prompts in the audit log instead of storing them?**
The dashboard and cost reporting never need the actual prompt text — they
need tier, model, cost, latency, and quality score. Storing a hash keeps
the audit trail useful for debugging ("did this exact prompt happen
before?") without creating a second, less-protected copy of user content.

**Why is verification asynchronous rather than blocking the response?**
Verification exists to catch and improve routing decisions over time, not
to gate every individual response — that would erase the whole latency and
cost benefit of routing to a cheap model in the first place. It runs after
the user already has their answer.

## 3. Data flow diagram (component responsibilities)

| Component | Input | Output | File |
|---|---|---|---|
| Feature extractor | raw prompt string | numeric feature dict | `app/classifier/features.py` |
| Classifier | feature vector | tier (1/2/3) | `app/classifier/classifier.py` |
| Router | prompt | model name + reason | `app/routing/router.py` |
| Provider abstraction | prompt + model config | standardized `Response` | `app/models/providers.py` |
| Logger | request + response data | SQLite row | `app/logging_db/db.py` |
| Verifier | prompt + candidate response | quality score + escalation flag | `app/verification/verifier.py` |
| Dashboard | SQLite table | charts + headline savings number | `app/dashboard/streamlit_app.py` |

## 4. Known limitations (stated plainly, not hidden)

- The classifier is trained on a templated seed dataset (see README), so
  its real-world accuracy on genuinely novel prompts will likely be lower
  than the 81% measured on held-out seed data.
- The verifier's LLM-as-judge approach is a reasonable default, not the
  only valid one — for classification-type tasks, exact-match against the
  reference model's label would be cheaper and less ambiguous than a 1–5
  judge score. The build guide's Phase 3 step 1 calls for use-case-specific
  thresholds; this implementation ships one general-purpose judge prompt
  and notes that as a simplification.
- There's no automated retraining loop wired up yet (see README's "suggested
  next features") — the plumbing (escalation events land in the database)
  is there, but the "retrain weekly" cron job described in Phase 3 step 4
  is not implemented in this codebase.
