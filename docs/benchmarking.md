# OCM Benchmarking Guide

How to run comprehensive benchmarks against the OCM stack and interpret the results.

## Why benchmark

OCM's spec is built on testable claims — every locked decision in `docs/superpowers/specs/2026-05-08-ocm-v1-design-spec.md` references either a measured number (e.g., "vLLM RTX 4090 ~120 tok/s") or a hypothesis that needs validation (e.g., "Effective-Context Triad beats frontier 1M-token at 200× lower per-query cost"). The bench framework is how those claims become evidence — or get refuted, which is just as useful.

## Mental model

The framework has two levels:

### Sandboxes

A **sandbox** is one isolated test of one hypothesis. It lives at:

```
bench/isolation/<category>/<sandbox-name>/
  expected.json     # the hypothesis + thresholds + decision rule
  README.md         # what it measures + how to interpret
  bench.py          # ACTIVE only — produces outputs.json with measurements
  docker-compose.yml # ACTIVE only — declares dependencies
```

Each sandbox emits a verdict per run: **CONFIRMED**, **REFUTED**, or **INCONCLUSIVE**. Verdicts are computed from `expected.json` thresholds:

```jsonc
{
  "metric": "tokens_per_second_median_single_stream",
  "thresholds": {
    "confirm_at_least": 100.0,
    "refute_below": 80.0
  }
}
// Run produces 124.3 tok/s -> CONFIRMED
// Run produces 65.1 tok/s -> REFUTED
// Run produces 90.2 tok/s -> INCONCLUSIVE
```

### ACTIVE vs INACTIVE

- **ACTIVE** sandboxes have a working `bench.py` + `docker-compose.yml` and run end-to-end. Today: 1 (`vllm-q4-llama8b`).
- **INACTIVE** sandboxes are slot stubs with only `expected.json` + `README.md` — committed early so the harness has targets when underlying tech matures (mesh transport for multipass-fleet, Memory Palace for Sandbox F, etc.). Today: 13.

The runner respects `status: "INACTIVE"` and skips them with a clear log line. See spec v0.6 row 32 for the rationale.

## Running benchmarks

### Setup (one-time)

```bash
cd bench
pip install -e .
# Docker is required to actually execute ACTIVE sandboxes.
# Without Docker, dry-run still validates structure.
```

### Single sandbox

```bash
# Validate without running anything
bench run isolation/inference-engines/vllm-q4-llama8b \
  --hardware-class nvidia-rtx-4090-24gb --dry-run

# Real measurement (3 repeats by default)
bench run isolation/inference-engines/vllm-q4-llama8b \
  --hardware-class nvidia-rtx-4090-24gb
```

### Comprehensive: all ACTIVE sandboxes

```bash
bench run-all --hardware-class nvidia-rtx-4090-24gb
```

This walks every sandbox, skips INACTIVE ones with a log line, runs each ACTIVE one with the same hardware class and repeats, and produces a unified comparison table at the end:

```
RUN    isolation/inference-engines/vllm-q4-llama8b  (vllm-q4-llama8b-singlestream-tps)
  -> CONFIRMED primary=124.300
SKIP   isolation/memory/mem0-v3-locomo (INACTIVE)
SKIP   isolation/mesh-transport/multipass-fleet (INACTIVE)
...

OCM Bench: comparison on nvidia-rtx-4090-24gb
+------------------------------------------+-------------------------+-----------+----------------+--------------------+
| Sandbox                                  | Hypothesis              | Verdict   | Primary median | Secondary median   |
+------------------------------------------+-------------------------+-----------+----------------+--------------------+
| isolation/inference-engines/vllm-q4-...  | vllm-q4-llama8b-tps     | CONFIRMED | 124.300        | 1.234              |
+------------------------------------------+-------------------------+-----------+----------------+--------------------+

1 CONFIRMED  0 REFUTED  0 INCONCLUSIVE  13 INACTIVE skipped  0 errored
```

Exit codes: **0** if all clean, **1** if any REFUTED, **2** if any errored (and `--continue-on-error` wasn't passed).

### Reports across past runs

```bash
# Aggregate verdicts across the last 20 runs of any sandbox
bench report

# Filter to a specific hypothesis
bench report --hypothesis-id vllm-q4-llama8b-singlestream-tps

# Filter to a hardware class
bench report --hardware-class nvidia-rtx-4090-24gb
```

## Hardware classes

A **hardware class** is an opaque tag that groups results by the machine they ran on. Don't try to make this ontologically clean — just be consistent. Examples currently in use:

| Class | Approximate spec |
|---|---|
| `nvidia-rtx-4090-24gb` | RTX 4090 24 GB on AM5 / LGA1700 desktop |
| `nvidia-rtx-5090-32gb` | RTX 5090 32 GB Blackwell |
| `apple-m4-pro-32gb` | Mac Mini M4 Pro / MacBook Pro 14" base |
| `apple-m4-max-128gb` | Mac Studio M4 Max upper config |
| `cpu-only-32gb` | Any CPU-only setup, no GPU available |
| `ci-validation` | Reserved for `dry-run-all` in CI — never produces real results |

If you run on hardware that doesn't fit, invent a tag and use it consistently across runs. The framework doesn't enforce a registry on purpose — the user knows their hardware better than we do.

## Interpreting verdicts

| Verdict | What it means | What to do |
|---|---|---|
| **CONFIRMED** | Primary metric crossed the `confirm_at_least` (or `_at_most`) threshold | The hypothesis holds on this hardware. Lock the corresponding spec decision if not already locked |
| **REFUTED** | Primary metric crossed the `refute_below` (or `_above`) threshold | The hypothesis fails on this hardware. Investigate per the sandbox's `decision_rule` |
| **INCONCLUSIVE** | Result fell between confirm + refute thresholds | Variance too high or threshold too tight. Rerun with more repeats or different prompt mix |

REFUTED is not a failure — it's a successful experiment. Spec decisions that survive REFUTATIONS get stronger. Spec decisions that get REFUTED need revisiting.

## Disconfirmation sandboxes

Some sandboxes are designed to CONFIRM a *negative* — e.g., `letta-tool-memory` expects to confirm Letta-on-8B performs poorly, vindicating the v0.2 swap to Mem0. Read each sandbox's README for what its expected outcome is.

## What CI runs

`.github/workflows/bench.yml` runs `bench dry-run-all` on every PR that touches `bench/`. This validates structure but doesn't execute. Real benchmarks happen on developer hardware (or eventually a self-hosted runner with GPUs).

There's no auto-bench-on-every-PR by design — bench runs are expensive in time + bandwidth + GPU minutes. They're scheduled manually when:

- A spec decision is being locked (need evidence)
- A regression is suspected (rerun a CONFIRMED sandbox)
- A milestone is being cut (re-validate everything)
- A new sandbox flips ACTIVE (validate the harness works)

## Sandbox catalog (as of 2026-05-09)

### ACTIVE (1)

| Sandbox | What |
|---|---|
| `inference-engines/vllm-q4-llama8b` | vLLM v1 + AWQ-INT4 Llama 3.1 8B single-stream tok/s on RTX 4090 |

### INACTIVE: memory layer (3)

| Sandbox | Hypothesis |
|---|---|
| `memory/mem0-v3-locomo` | Mem0 v3 ≥88 LoCoMo recall on Qwen3 8B Q4 |
| `memory/mem0-v3-memoryarena` | ≥55% on Stanford MemoryArena interdependent tasks |
| `memory/letta-tool-memory` | Letta tool-driven ≤70% on Llama 8B (disconfirmation) |

### INACTIVE: retrieval (3)

| Sandbox | Hypothesis |
|---|---|
| `retrieval/aider-repomap-fidelity` | Repomap ≥85% accuracy at 30% tokens |
| `retrieval/continuedev-hybrid-retrieval` | Hybrid stack ≥10pp over pure-vector RAG |
| `retrieval/cognee-8b-graph-quality` | Cognee on 8B hallucinates ≥80% (disconfirmation) |

### INACTIVE: optimization (1)

| Sandbox | Hypothesis |
|---|---|
| `optimization/dspy-gepa-skill-portability` | GEPA-compiled programs preserve ≥95% accuracy across nodes |

### INACTIVE: mesh transport (1)

| Sandbox | Hypothesis |
|---|---|
| `mesh-transport/multipass-fleet` | 5-node Multipass fleet 2-hop chat under 500ms median |

### INACTIVE: frontier comparison (5)

| Sandbox | Hypothesis |
|---|---|
| `frontier-comparison/sandbox-e-schema-compression` | MCP schema compression 30-60% tokens at ≤2pp accuracy loss |
| `frontier-comparison/sandbox-f-memory-palace-effective-corpus` | OCM full-stack ≥92% on long-horizon QA at ≤8K tokens vs frontier 1M-token |
| `frontier-comparison/sandbox-g-wire-compression` | zstd-6 mesh ≥60% bandwidth reduction at ≤2ms overhead |
| `frontier-comparison/sandbox-h-fp8-activation-transfer` | fp8 ≥99% fp16 quality at half bandwidth (gates v6) |
| `frontier-comparison/sandbox-i-mem0-encryption-overhead` | SQLCipher AES-256 ≤15% latency, no accuracy regression |

## Adding a new sandbox

1. Pick the right category — make a new one if needed
2. Mirror an existing sandbox's structure
3. Write `expected.json` with explicit thresholds + `decision_rule`
4. Write a focused README — what it measures, what it doesn't, how to interpret
5. If you have a working harness, add `bench.py` + `docker-compose.yml` and set `status: "ACTIVE"`. If not, leave `status: "INACTIVE"` and document `blocked_on`
6. `bench dry-run-all` should pass

See `bench/isolation/inference-engines/vllm-q4-llama8b/` for the canonical example of an ACTIVE sandbox.

## Reading the existing results

After a run, results land in `bench/results/<hypothesis_id>/<timestamp>.json`. Each file has the full `SandboxSummary`:

```json
{
  "hypothesis_id": "vllm-q4-llama8b-singlestream-tps",
  "hardware_class": "nvidia-rtx-4090-24gb",
  "timestamp_utc": "2026-05-09T20:30:15.123456+00:00",
  "expected": { /* the hypothesis */ },
  "runs": [{"repeat_index": 0, "primary_value": 124.3, "secondary_value": 1.2, ...}, ...],
  "primary_median": 124.3,
  "primary_std": 2.1,
  "verdict": "CONFIRMED",
  "verdict_reason": "primary_median 124.30 >= confirm_at_least 100.00"
}
```

`bench report` aggregates these into a readable cross-run table.

## Related docs

- [`docs/release-process.md`](release-process.md) — how OCM tags + ships releases (bench results inform whether to ship)
- [`docs/superpowers/specs/2026-05-08-ocm-v1-design-spec.md`](superpowers/specs/2026-05-08-ocm-v1-design-spec.md) — every spec lock that bench validates
- [`docs/superpowers/plans/2026-05-08-ocm-bench-framework-plan.md`](superpowers/plans/2026-05-08-ocm-bench-framework-plan.md) — original framework design
