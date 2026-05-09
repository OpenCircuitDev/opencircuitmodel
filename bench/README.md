# OCM Bench Framework

Hypothesis → sandbox → measure → verdict (CONFIRMED / REFUTED / INCONCLUSIVE).

This framework is the engineering discipline that prevents OCM from making spec
decisions based on vendor claims. Every locked decision in the OCM design spec
gets a benchmark. Every benchmark is reproducible. Every result is versioned.

## Quick start

```bash
# Install
cd bench
pip install -e ".[dev]"

# List sandboxes
bench list

# Validate sandbox structure (no Docker invocation)
bench run isolation/inference-engines/vllm-q4-llama8b --hardware-class nvidia-rtx-4090-24gb --dry-run

# Run all sandboxes through dry-run (CI-friendly)
bench dry-run-all

# Run a real benchmark (Docker required)
bench run isolation/inference-engines/vllm-q4-llama8b --hardware-class nvidia-rtx-4090-24gb --repeats 3

# Retro-sync report
bench report --hypothesis-id mem0-v3-llama8b-locomo
```

## Sandbox structure

Every sandbox lives at `isolation/<category>/<tool>/` or `combination/<name>/`
and contains exactly four files:

- `expected.json` — hypothesis with confirm + refute thresholds, comparison anchor, decision rule
- `docker-compose.yml` — sandbox container spec
- `bench.py` — measurement script (writes outputs.json with primary_value)
- `README.md` — what this measures, what it doesn't, how to interpret

See [`isolation/inference-engines/vllm-q4-llama8b/`](isolation/inference-engines/vllm-q4-llama8b/)
for the canonical example.

## Verdict logic

Each sandbox declares confirm + refute thresholds in `expected.json`. After
`repeats` runs, the median primary metric is compared:

- **CONFIRMED** — median ≥ confirm_at_least (or ≤ confirm_at_most)
- **REFUTED** — median < refute_below (or > refute_above)
- **INCONCLUSIVE** — between thresholds, or no applicable threshold pair

Secondary thresholds can demote a CONFIRMED primary verdict to INCONCLUSIVE
or REFUTED if cost/latency exceeds bounds.

## Honesty principles

- **No cherry-picked numbers.** Median of N≥3 minimum; std-dev reported.
- **No moving goalposts.** `expected.json` is locked at sandbox creation; results scored against original hypothesis.
- **REFUTED is celebrated.** When a benchmark refutes a research claim, the framework is doing its job.
- **INCONCLUSIVE is a valid verdict.** When data is noisy or threshold is borderline, no forced binary outcome.
- **Every published number is reproducible.** Anyone can `git clone && bench run` and verify.

## Hardware classes

Benchmarks are tagged with hardware class so retro-sync queries compare apples-to-apples:

- `nvidia-rtx-4060-8gb`
- `nvidia-rtx-4090-24gb`
- `nvidia-rtx-5090-32gb`
- `apple-m4-base-16gb`
- `apple-m4-pro-32gb`
- `apple-m4-pro-64gb`
- `apple-m2-ultra-192gb`
- `cpu-only-32gb`

## Architecture

See [`docs/superpowers/plans/2026-05-08-ocm-bench-framework-plan.md`](../docs/superpowers/plans/2026-05-08-ocm-bench-framework-plan.md)
for the full design.

## Tests

```bash
pytest tests/ -v
```

All 25+ tests must pass before merging changes to the framework code.
