"""Measure vLLM v1 + AWQ-INT4 Llama 3.1 8B single-stream throughput.

Runs first 50 prompts from /workloads/chat-singleturn-1k.jsonl through
vLLM's OpenAI-compat streaming endpoint and reports:
  primary_value: median tokens/sec across the 50 prompts
  secondary_value: p50 time-to-first-token (seconds)
"""

from __future__ import annotations

import asyncio
import json
import os
import statistics
import time
from pathlib import Path

import httpx

VLLM_URL = os.environ.get("VLLM_URL", "http://localhost:8000")
WORKLOAD_PATH = Path(os.environ.get("WORKLOAD_PATH", "/workloads/chat-singleturn-1k.jsonl"))
MODEL = "hugging-quants/Meta-Llama-3.1-8B-Instruct-AWQ-INT4"
MAX_TOKENS = 256
SAMPLE_SIZE = 50


async def measure_one(client: httpx.AsyncClient, prompt: str) -> dict | None:
    body = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": MAX_TOKENS,
        "stream": True,
        "temperature": 0.7,
    }
    t0 = time.monotonic()
    first_token_time: float | None = None
    output_tokens = 0
    try:
        async with client.stream(
            "POST",
            f"{VLLM_URL}/v1/chat/completions",
            json=body,
            timeout=120,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                line = line.strip()
                if not line.startswith("data: "):
                    continue
                payload = line[6:]
                if payload == "[DONE]":
                    break
                try:
                    chunk = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                if delta:
                    if first_token_time is None:
                        first_token_time = time.monotonic()
                    output_tokens += max(1, len(delta) // 4)  # crude token estimate
        t_end = time.monotonic()
    except httpx.HTTPError:
        return None
    if first_token_time is None or output_tokens == 0:
        return None
    return {
        "ttft_seconds": first_token_time - t0,
        "decode_seconds": t_end - first_token_time,
        "output_tokens": output_tokens,
        "tokens_per_second": output_tokens / max(t_end - first_token_time, 1e-6),
    }


async def main() -> None:
    if not WORKLOAD_PATH.exists():
        raise SystemExit(f"workload file missing at {WORKLOAD_PATH}")
    prompts: list[str] = []
    for line in WORKLOAD_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        prompts.append(row["prompt"])
        if len(prompts) >= SAMPLE_SIZE:
            break

    results: list[dict] = []
    overall_t0 = time.monotonic()
    async with httpx.AsyncClient() as client:
        for prompt in prompts:
            result = await measure_one(client, prompt)
            if result is not None:
                results.append(result)
    overall_seconds = time.monotonic() - overall_t0

    if not results:
        SystemExit("no successful runs")

    tps_values = [r["tokens_per_second"] for r in results]
    ttft_values = [r["ttft_seconds"] for r in results]
    primary = statistics.median(tps_values)
    secondary = statistics.median(ttft_values)

    payload = {
        "primary_value": primary,
        "secondary_value": secondary,
        "duration_seconds": overall_seconds,
        "n_successful": len(results),
        "n_attempted": len(prompts),
    }
    Path("/work/outputs.json").write_text(json.dumps(payload, indent=2))
    print(f"median tok/s: {primary:.1f}")
    print(f"median TTFT seconds: {secondary:.3f}")
    print(f"successful: {len(results)}/{len(prompts)}")


if __name__ == "__main__":
    asyncio.run(main())
