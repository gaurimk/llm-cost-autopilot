"""
Load Test
==========
Sends a batch of diverse prompts through the running API (default:
http://localhost:8000) and prints a final cost-savings summary. This is
the script referenced in Phase 6 of the build guide -- run it, then screenshot
the dashboard and pull /v1/stats for your portfolio case study.

Usage:
    python scripts/load_test.py --n 500 --base-url http://localhost:8000
"""

import argparse
import asyncio
import random
import time

import httpx

from data.generate_seed_dataset import generate as generate_prompts


async def send_one(client: httpx.AsyncClient, base_url: str, prompt: str):
    try:
        resp = await client.post(f"{base_url}/v1/completions", json={"prompt": prompt}, timeout=60)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        return {"error": str(exc)}


async def run(n: int, base_url: str, concurrency: int):
    pool = generate_prompts(n_per_tier=max(1, n // 3))
    prompts = [row["prompt"] for row in pool][:n]
    random.shuffle(prompts)

    results = []
    sem = asyncio.Semaphore(concurrency)

    async def bound_send(client, prompt):
        async with sem:
            return await send_one(client, base_url, prompt)

    start = time.perf_counter()
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(*(bound_send(client, p) for p in prompts))
    elapsed = time.perf_counter() - start

    errors = [r for r in results if "error" in r]
    ok = [r for r in results if "error" not in r]

    print(f"Sent {len(prompts)} prompts in {elapsed:.1f}s ({len(ok)} ok, {len(errors)} errors)")
    if ok:
        total_cost = sum(r["cost"] for r in ok)
        print(f"Total cost across load test: ${total_cost:.4f}")

    print("\nFetching final stats from /v1/stats ...")
    async with httpx.AsyncClient() as client:
        stats_resp = await client.get(f"{base_url}/v1/stats")
        print(stats_resp.json())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=500, help="Number of prompts to send (500-1000 recommended)")
    parser.add_argument("--base-url", type=str, default="http://localhost:8000")
    parser.add_argument("--concurrency", type=int, default=10)
    args = parser.parse_args()

    asyncio.run(run(args.n, args.base_url, args.concurrency))
