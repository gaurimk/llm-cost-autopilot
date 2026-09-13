"""
Seed Dataset Generator
========================
Generates a STARTER labeled dataset of prompts across the three complexity
tiers, using templates. This exists so the project is runnable end-to-end
out of the box.

IMPORTANT / HONESTY NOTE (see docs/DEVELOPER_GUIDE.md):
The build guide calls for 200+ HAND-labeled prompts. Templated data is a
reasonable bootstrap for wiring the pipeline together, but it is easier for
a model to learn than real, messy user traffic. Before you rely on this
classifier for a real cost decision, replace or expand this seed set with
prompts hand-labeled from your own traffic logs.

Tiers:
  1 = simple   (reformatting, extraction, basic Q&A from provided context)
  2 = moderate (summarization, classification, structured analysis)
  3 = complex  (multi-step reasoning, creative generation, nuanced judgment)
"""

import csv
import random
from pathlib import Path

random.seed(7)

TIER_1_TEMPLATES = [
    "Extract the email address from this text: {ctx}",
    "What is the capital of {country}?",
    "Convert this list to a comma-separated string: {list_items}",
    "Reformat this date {date} into YYYY-MM-DD format.",
    "Given the following context, what is the customer's order number? {ctx}",
    "Extract all phone numbers from this text: {ctx}",
    "What year did {event} happen?",
    "Turn this JSON into a bulleted list: {ctx}",
    "Uppercase every word in this sentence: {ctx}",
    "Given the table below, what is the value in row 2? {ctx}",
]

TIER_2_TEMPLATES = [
    "Summarize the following article in 3 sentences: {ctx}",
    "Classify this support ticket as billing, technical, or account: {ctx}",
    "Given these reviews, extract the overall sentiment and 3 key themes: {ctx}",
    "Organize the following notes into a structured outline: {ctx}",
    "Summarize the key differences between {a} and {b}.",
    "Given this transcript, list the action items discussed: {ctx}",
    "Classify each of these emails as spam or not spam: {ctx}",
    "Turn these meeting notes into a structured status report: {ctx}",
    "Summarize this contract clause in plain language: {ctx}",
    "Given this dataset description, suggest an appropriate chart type.",
]

TIER_3_TEMPLATES = [
    "Analyze the tradeoffs between {a} and {b} for a startup deciding on {topic}, and recommend one with justification.",
    "Design a system architecture for {topic} that handles {constraint}.",
    "Write a short story about {topic} that explores the theme of {theme}.",
    "Critique this business plan and recommend three specific improvements: {ctx}",
    "Given conflicting stakeholder priorities ({a} vs {b}), propose a compromise strategy for {topic}.",
    "Debate the ethical implications of {topic} from two opposing viewpoints.",
    "Given this codebase description, design a migration plan from {a} to {b} with rollback steps.",
    "Synthesize insights from these three reports and recommend a Q3 strategy for {topic}.",
    "Write a nuanced performance review for an employee who is strong at {a} but struggles with {b}.",
    "Propose an experiment design to test whether {topic} improves {a}, including controls for {constraint}.",
]

FILLERS = {
    "country": ["France", "Japan", "Brazil", "Kenya", "Canada", "India"],
    "list_items": ["apple, banana, cherry", "red, green, blue", "north, south, east, west"],
    "date": ["03/14/2024", "12-25-2023", "July 4, 2025"],
    "event": ["the moon landing", "the fall of the Berlin Wall", "the first iPhone launch"],
    "ctx": [
        "Order #4471 was placed by Jane Doe on Tuesday, contact jane.doe@example.com.",
        "The meeting covered budget, hiring, and Q3 roadmap; contact ops@example.com for details.",
        "Customer reports login failures since the last update and wants a refund.",
        "The quarterly report shows revenue up 12% and churn down 3% versus last quarter.",
    ],
    "a": ["microservices", "a monolith", "Python", "Rust", "remote work", "in-office work"],
    "b": ["a monolith", "microservices", "Rust", "Python", "in-office work", "remote work"],
    "topic": [
        "an LLM routing platform", "a fintech onboarding flow", "a healthcare scheduling app",
        "a recommendation engine", "a supply chain optimizer",
    ],
    "constraint": ["sub-200ms latency", "GDPR compliance", "a fixed $500/month budget", "offline usage"],
    "theme": ["isolation", "trust", "ambition", "change"],
}


def fill(template: str) -> str:
    out = template
    for key, options in FILLERS.items():
        if "{" + key + "}" in out:
            out = out.replace("{" + key + "}", random.choice(options))
    return out


def generate(n_per_tier: int = 25):
    rows = []
    for tier, templates in [(1, TIER_1_TEMPLATES), (2, TIER_2_TEMPLATES), (3, TIER_3_TEMPLATES)]:
        for _ in range(n_per_tier):
            template = random.choice(templates)
            prompt = fill(template)
            rows.append({"prompt": prompt, "tier": tier})
    random.shuffle(rows)
    return rows


if __name__ == "__main__":
    rows = generate(n_per_tier=70)  # 210 rows total seed set
    out_path = Path(__file__).parent / "training_prompts.csv"
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["prompt", "tier"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} labeled prompts to {out_path}")
