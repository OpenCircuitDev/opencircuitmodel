# Sandbox: mem0-v3-locomo

**Hypothesis:** Mem0 v3 (library-driven retrieval) achieves ≥88 LoCoMo recall
on a small-model setup (llama3 8B Q4 + Mem0 v3 + faiss-cpu), within 4 points
of the published 91.6 figure on larger models. Library-driven retrieval is the
directly-aligned pattern for the small-model thesis.

**Status:** ACTIVE — verdict pending.

## What this measures

- **LoCoMo recall**: standard multi-session long-conversation memory benchmark
  across 10 conversations (5,882 turns, 1,986 QA items). Per-QA recall =
  |retrieved dia_ids ∩ evidence dia_ids| / |evidence dia_ids|.
  `locomo_recall_score` = mean over conversations × 100.
- **tokens_retrieved_p50**: median per-QA token count injected as retrieval
  context (true flat median over all 1,986 QA items; 4 chars ≈ 1 token).

## What this does NOT measure

- Multi-session interdependent task quality — that's MemoryArena
  (`memory/mem0-v3-memoryarena`)
- Generation quality on retrieved context — orthogonal; see chat-quality sandboxes
- Agent-driven memory orchestration — that's Letta's paradigm (`memory/letta-tool-memory`)

## How to interpret

| Verdict | What it means |
|---|---|
| CONFIRMED | Library-driven retrieval is structurally aligned with small-model thesis; v0.4 row 9 lock holds |
| REFUTED on recall | Investigate llama3 8B's retrieval-context utilization or Mem0 v3 config tuning |
| REFUTED on tokens | 7000 token budget is too optimistic; revisit Effective-Context Triad quick-look-up budget |
| INCONCLUSIVE | Variance too high; expand workload size or repeat count |

## Dataset

LoCoMo — Maharana et al., *Evaluating Very Long-Term Conversational Memory of
LLM Agents*, ACL 2024 ([arXiv:2402.17753](https://arxiv.org/abs/2402.17753)).
Repository: [snap-research/locomo](https://github.com/snap-research/locomo),
licensed **CC BY-NC 4.0**.

We download `locomo10.json` from the official snap-research/locomo repository
at run time (SHA-pinned to commit `cbfbc1dba6bc53d00625212a0f22d55ffee7c1fc`)
and do **not** redistribute it. Use is non-commercial benchmarking of OCM's
library-driven retrieval pattern (spec row 9). Attribution per CC BY-NC 4.0
requirements.

## Run

The bench framework runs this sandbox via `docker compose up` per the standard
contract. Manual one-off:

```bash
cd bench/isolation/memory/mem0-v3-locomo
docker compose run --rm bench
```

With the optional LLM-in-the-loop diagnostic (requires Ollama with `llama3`
pulled on the host):

```bash
docker compose run --rm bench python bench.py --with-llm
```

The verdict path (default, no `--with-llm`) runs in ~6-8 minutes per repeat,
~18-25 minutes for the standard 3 repeats. No Ollama required for the verdict.

## Source for the claim

Mem0 v3 release notes (April 2026), pinned in research note
`docs/superpowers/research/2026-05-09-decentralized-memory-palace-pattern.md`.

---

## Verdicts

**Run 1 — 2026-06-11 (operator dev box, Windows/Docker, CPU)**

| Field | Value |
|---|---|
| `locomo_recall_score` | **30.79** |
| Verdict | **REFUTED** (contract: confirm ≥88 · refute <80) |
| Per-conversation recall | 0.293 / 0.245 / 0.282 / 0.179 / 0.552 / 0.354 / 0.366 / 0.388 / 0.266 / 0.154 |
| tokens_p50 | 254 |
| Elapsed | 4,364s measurement (~73 min total incl. install) |
| Config | mem0ai 2.0.5 · MiniLM-L6-v2 · faiss (BM25 hybrid DISABLED — faiss lacks keyword search) · no spaCy · `add(infer=False)` · top_k=10 |
| Provenance | locomo10.json SHA-pinned `cbfbc1d…` · branch feat/mem0-v3-locomo-activation |

**What this refutes — and what it does not.** This REFUTES "library-driven retrieval
in the hermetic pure-vector config reaches published-Mem0 recall at LoCoMo scale."
It does NOT refute the memory thesis (amnesia-ab: 94.2% at small scale) or Mem0's
production config — which adds exactly what this config strips: BM25+entity tri-signal
rank fusion and LLM fact extraction (`infer=True`). External evidence (Hindsight,
arXiv 2512.12818) shows hybrid-fusion + a 22M cross-encoder reranker reaches ~89.6
LoCoMo with open models. The decision rule's "investigate config tuning" branch fires:
next iteration = BM25 sidecar + RRF + reranker + a 2026-class embedder, re-run this
same contract. A REFUTED first verdict on a stripped config is the framework working.

