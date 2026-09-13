# I Built an AI System That Routes Requests to the Cheapest Model That Can Handle Them

Every team running LLMs at scale eventually hits the same uncomfortable
realization: they're sending simple requests to expensive models. Someone
asks the system to reformat a date or pull an email address out of some
text, and it gets routed to the same top-tier model that handles genuinely
hard reasoning tasks — the equivalent of calling a specialist surgeon for
a splinter. It works, but it wastes money at volume.

So I built LLM Cost Autopilot: a routing layer that sits in front of
multiple AI providers, figures out how hard each incoming request
actually is, and sends it to the cheapest model that can handle it well —
while continuously checking its own decisions to make sure quality never
quietly degrades.

## How it works

The system has four moving parts that hand off to each other in sequence.

**A complexity classifier** looks at each incoming prompt and labels it
Simple, Moderate, or Complex, based on features like length, whether it
contains words like "analyze" or "compare," and how many constraints it
places on the answer. A lightweight logistic regression model handles this
— not a work of ML art, just accurate enough to make a good routing
skeleton (81% held-out accuracy, just above the bar I set for a first
version).

**A router** takes that tier and looks up which model should handle it, using
a plain YAML config file. In the configuration I validated, Simple and
Moderate tasks go to GPT-4o-mini, and Complex tasks go to full GPT-4o — the
routing map also supports a free, locally-hosted Llama model and Anthropic's
Claude models, but I only had an OpenAI key on hand when I ran this, so I
pointed every tier at OpenAI for now. Because the mapping lives in a config
file instead of code, swapping in Claude or a local model later is a
one-line change, not a redeploy.

**A unified provider layer** hides the fact that OpenAI, Anthropic, and a
local Ollama instance all have different APIs. Every model call comes back
in the same shape — text, tokens used, latency, cost — so the rest of the
system stays provider-agnostic.

**An async quality verifier** is the part I think matters most. After the
user already has their answer — zero added latency — a background job
re-sends the same prompt to a high-quality reference model and scores how
well the cheap model's answer holds up. If it doesn't, that's logged as a
routing failure. The plumbing is there to feed those failures back into
the classifier's training data over time, closing the loop between "we
saved money" and "we didn't sacrifice quality to do it."

Everything gets logged to a SQLite audit trail, which feeds a dashboard
showing the number that actually matters to a business: total cost versus
what it would have cost if every request went to the most expensive model.
That percentage is the headline metric — it's the number a VP of
Engineering or a CFO immediately understands, even if they've never heard
the word "logistic regression."

## The number, from an actual test run

On a validation batch of 36 real requests against live OpenAI models, the
system cut cost by **44.8%** compared to routing everything to GPT-4o,
while the async verifier kept independently checking that the cheaper
model's answers still held up. This is a small test batch, not a
large-scale benchmark — I'm reporting it as exactly that, rather than
inflating it into a claim about performance at scale. The mechanism that
produced this number (tiered routing + continuous quality verification) is
the same mechanism that would produce savings at higher volume; I just
haven't run the larger load test yet to confirm the number holds.

## What I'd tell you honestly

Three things in this build are deliberately starter material or scoped
narrowly, not finished production claims. First, the labeled training data
the classifier learns from is templated rather than 200+ prompts I
hand-labeled from real traffic — templated data is easier for a model to
learn than messy real-world requests, so I'd expect actual accuracy on live
traffic to be lower until it's replaced with real examples. Second, the
pricing figures for each model are illustrative snapshots, not a live
pricing feed — they need to be checked against each provider's current
pricing before anyone makes a financial decision based on them. Third, the
44.8% savings figure above is validated on a 36-request test batch, not the
500-1,000 request load test a full portfolio piece would ideally include —
I'm stating that scope plainly rather than presenting a small test as if it
were a large-scale benchmark.

I think that honesty is part of the point. This project isn't interesting
because it's a clever way to call AI APIs — it's interesting because it
treats AI cost the way an operations team would: measured, capped, and
continuously verified, not accepted as a fixed line item. That's the gap
between "I can use an LLM API" and "I understand how to run one at scale
responsibly."

The full project — router, classifier, verifier, dashboard, API, and
Docker setup — is available as open source, with docs for developers,
stakeholders, and anyone in between.