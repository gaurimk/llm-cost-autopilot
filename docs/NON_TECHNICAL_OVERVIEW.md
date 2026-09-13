# LLM Cost Autopilot — Overview for Non-Technical Readers

## The problem, in plain terms

Companies that use AI language models (like ChatGPT or Claude) to power
features in their products often send *every* request to the same,
expensive, top-tier model — even simple ones. That's like hiring a
surgeon to put on a Band-Aid. It works, but it costs far more than it
needs to.

**What this project builds:** a smart middle layer that looks at each
incoming request, decides how difficult it actually is, and sends it to
the cheapest AI model that can handle it well. Simple requests ("extract
this email address") go to a cheap, fast model. Genuinely hard requests
("write a nuanced comparison of two business strategies") go to the
expensive, powerful model. The system also constantly double-checks its
own decisions and gets smarter over time.

## Why this matters, using an analogy

Think of a hospital triage desk. Not every patient needs to see the chief
surgeon — a nurse can handle a scraped knee, a general physician can
handle a cold, and only the surgeon handles the surgery. A good triage
system routes each patient to the *right level of expertise*, which is
faster and cheaper for everyone, without compromising care for the people
who genuinely need the specialist.

This project is that triage desk, but for AI requests instead of
patients.

## How it works, step by step (no jargon)

1. **A request comes in.** Someone (or some other piece of software) asks
   the system a question or gives it a task.
2. **The system rates the difficulty.** It looks at things like: how long
   is the request? Does it use words like "analyze" or "compare" that
   suggest real thinking is needed? Is it just asking to reformat some
   text? Based on this, it labels the request as Simple, Moderate, or
   Complex.
3. **It picks the right AI model for that difficulty level.** Simple
   requests go to a free, locally-run AI model. Moderate requests go to a
   mid-priced model. Complex requests go to the most capable (and most
   expensive) model.
4. **The answer comes back to the user immediately** — there's no extra
   waiting for the next step.
5. **Behind the scenes, a quality check runs.** After the user already has
   their answer, the system quietly double-checks: "did the cheap model's
   answer actually hold up compared to what the best model would have
   said?" If not, that's flagged.
6. **The system keeps a full audit trail** of every request: what it
   cost, which model handled it, and how good the answer was. This
   feeds a dashboard that shows, in dollar terms, how much money the
   system is saving compared to sending everything to the expensive
   model.

## What "success" looks like

The headline number this project is built to produce is something like:

> "This system cut AI costs by 60%, while keeping answer quality within
> an acceptable range of the most expensive model."

That single number — cost saved, with quality held steady — is what
makes this valuable to a business: it's not just a technical exercise, it
demonstrates thinking about AI the way a finance or operations leader
would.

## What's a demo vs. what's production-ready

To be transparent: this build includes a starter dataset used to teach
the difficulty-rating system what "simple" vs. "complex" looks like. That
starter set was generated from templates so the whole system runs
end-to-end out of the box — it is **not** the same as 200+ real examples
labeled by a person, which is what a production version would need. The
docs are explicit about this so no one mistakes the demo dataset for
production-validated data.

## Where to look for more detail

- Curious how the pieces fit together technically? See `ARCHITECTURE.md`.
- Want to run or extend the code? See `DEVELOPER_GUIDE.md`.
- Want a shareable summary of the project? See `BLOG_POST.md`.
