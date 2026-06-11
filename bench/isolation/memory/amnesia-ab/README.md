# amnesia-ab — memory ON vs OFF on an 8B local model

**Status: ACTIVE — first sandbox in the suite to actually run.**

## What this tests

The cheapest discriminating test of OCM's reason to exist. OCM's pitch is "a local model
that remembers you" — the central loop is library-driven retrieval (spec row 9): embed the
request, pull top-k memories, inject them, generate. If that loop does not make a small
local model *clearly* better on tasks that depend on prior-session facts, the
persistent-memory differentiator is refuted at small scale and nothing downstream matters.

## Method

Faithful **miniature** of the Mem0 library-driven pattern — NOT the OCM binaries (which
need a 3-process stack: daemon + inference server + Mem0). Same loop, operator's actual
hardware class:

- **Corpus:** 65 synthetic prior-session memories across 5 fictional projects
  (e-bike conversion, greenhouse controller, NAS build, drone gimbal, bakery side-business)
  plus personal preferences. Facts carry exact-matchable invented tokens (vendor names,
  numbers, dates) that an 8B model cannot guess — the other 4 projects act as retrieval
  distractors.
- **Tasks:** 20, each requiring 1-3 specific stored facts to answer well.
- **ARM A (ON):** task → mxbai-embed-large query embedding → cosine top-5 → injected as
  RELEVANT MEMORIES in the system prompt → llama3 8B Q4.
- **ARM B (OFF):** identical prompt, no memories.
- **Scoring:** objective substring match on key facts (normalized: lowercase, strip
  spaces/commas/periods). Retrieval hit = ≥2 of the task's source memories in top-5
  (or all, if the task has fewer than 2 sources).

## Hypothesis contract (expected.json)

| Metric | Confirm | Refute | Meaning on refute |
|---|---|---|---|
| `memory_on_fact_recall_pct` | ≥70 | <50 | 8B can't use injected memories — thesis fails on target hardware |
| `retrieval_hit_rate_pct` | ≥80 | <60 | embedding retrieval fails even at toy scale — memory layer needs redesign |
| `memory_off_fact_recall_pct` (sanity) | ≤25 | — | above 25 the corpus is guessable and the run is INVALID, not a confirm |

## Decision rule

- **CONFIRMED** → the core loop is valid at small scale. Justifies (1) the Ollama backend
  adapter in `ocm-inference`, (2) standing up the real Mem0-on-8B LoCoMo sandbox
  (`../mem0-v3-locomo`), (3) cutting the v0.1.0 release.
- **REFUTED** → archive-without-guilt evidence, before any further investment.

## Run

```
node run.mjs   # Ollama on 127.0.0.1:11434 with llama3 + mxbai-embed-large pulled
```

Results land in `results/run-<timestamp>.json` (summary + every prompt/output/score row).
