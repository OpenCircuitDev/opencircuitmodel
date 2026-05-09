# Sandbox E: Schema Compression Token Impact

**Hypothesis:** MCP tool-schema compression (strip descriptions, shorten param names, hide optional params) cuts per-request input tokens by 30-60% with ≤2pp tool-call-accuracy loss.

**Status:** INACTIVE — workload + tool-call accuracy harness not yet wired.

## Why this matters

Spec v0.2 row 21 locks schema compression as v1 default. This sandbox empirically validates the claimed 30-60% token reduction on representative tool-rich workloads. If the secondary metric (tool-call accuracy delta) blows past +5pp loss, the algorithm is too aggressive and the row 21 lock needs revisiting.

## Pair with

- `sandbox-a-raw-vllm-baseline` (when implemented) — comparison anchor
- `sandbox-c-aider-repomap` — orthogonal compression (structural, not schema)
- `sandbox-d-dspy-compiled` — orthogonal compression (behavioral, not schema)

## Source

Spec v0.2 row 21. Independent benchmarks of schema compression on Hermes-trained 8B models.
