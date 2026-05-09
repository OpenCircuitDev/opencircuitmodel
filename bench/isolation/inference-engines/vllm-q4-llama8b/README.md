# Sandbox: vllm-q4-llama8b

**Hypothesis:** vLLM v1 with AWQ-INT4 Llama 3.1 8B delivers ≥100 median tokens/sec single-stream on RTX 4090 24GB.

**Public claim being tested:** databasemart benchmark reports ~120 tok/s on this configuration.[^src]

[^src]: https://www.databasemart.com/blog/vllm-gpu-benchmark-rtx4090

## What this measures

- Median tokens-per-second across 50 single-turn prompts from `chat-singleturn-1k.jsonl`
- Median time-to-first-token (TTFT) as secondary metric
- Single-stream (concurrency=1) — does NOT measure batched throughput; that's a separate sandbox

## What this does NOT measure

- Multi-user concurrent throughput (use a separate sandbox with continuous batching)
- Tool-calling correctness (use BFCL v3 sandbox)
- Quality of output (use lm-eval-harness sandboxes)
- Wall-clock latency under contention (this is single-stream baseline only)

## How to interpret

| Verdict | What it means |
|---|---|
| CONFIRMED | vLLM + Q4 is the right v1 NVIDIA default; lock in the spec |
| REFUTED | Investigate quantization variant (Marlin vs default) and HF Hub mirror before declaring vLLM Q4 unsuitable |
| INCONCLUSIVE | Variance too high or threshold too tight; rerun with higher repeats or different prompt mix |

## How to run

Requires NVIDIA GPU + Docker + nvidia-container-toolkit on the host.

```bash
# Set HF_TOKEN if needed for the model download
export HF_TOKEN=<your-token>

# Validate structure (no Docker invocation)
bench run isolation/inference-engines/vllm-q4-llama8b --hardware-class nvidia-rtx-4090-24gb --dry-run

# Real measurement (3 repeats by default)
bench run isolation/inference-engines/vllm-q4-llama8b --hardware-class nvidia-rtx-4090-24gb
```

## Hardware classes verified for this sandbox

- `nvidia-rtx-4090-24gb` — primary target, claim is calibrated for this
- `nvidia-rtx-5090-32gb` — would be expected to confirm with margin (test once GPU is available)
- `nvidia-rtx-4060-8gb` — model doesn't fit in 8GB; sandbox will REFUTE on capacity
- `apple-m4-pro-32gb` — vLLM Apple Silicon path is immature; expected REFUTE
- `cpu-only-32gb` — no GPU; expected REFUTE

## Source for the claim

- vLLM RTX 4090 benchmark: https://www.databasemart.com/blog/vllm-gpu-benchmark-rtx4090
- Cross-reference: https://blog.premai.io/vllm-vs-sglang-vs-lmdeploy-fastest-llm-inference-engine-in-2026/
