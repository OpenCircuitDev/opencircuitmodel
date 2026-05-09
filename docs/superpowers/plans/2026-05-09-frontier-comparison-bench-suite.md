# Frontier-Comparison Benchmark Suite — Sandboxes A through E

> **Strategic question being tested:** Can OCM's mesh nature deliver frontier-class quality (Claude Opus 4.7 / GPT-5 tier) at sub-Mac-Mini per-user compute for a meaningful subset of tasks?
> **Status:** Plan only — implementation gates on bench framework scaffold (Track C) landing first.
> **Date:** 2026-05-09
> **Source thesis:** [Memory + sub-context retrieval deep-dive](../research/2026-05-09-memory-context-retrieval-deep-dive.md), plus the per-node efficiency stack-up from the [comprehensive synthesis](../research/2026-05-08-tool-landscape-synthesis.md).

This document specifies five new sandboxes (A through E) that together either confirm or refute OCM's most aggressive thesis: **the mesh structurally wins on specialization, persistence, and any task tolerant of higher wall-clock latency, while costing dramatically less per-user-query than running a frontier model directly.** If all five sandboxes CONFIRM, OCM's strategic position changes from "alternative" to "compete-on-quality."

---

## 1. The thesis being tested

There are five orthogonal mechanisms by which a mesh of consumer machines could match or exceed frontier-class single-machine quality:

1. **Distributed test-time scaling** — N samples across N nodes → majority vote / verifier-guided
2. **Tiered routing / model-borrowing** — easy queries local, hard queries route to a contributor's bigger node
3. **Skill federation** — DSPy GEPA-compiled programs shared across the mesh as signed artifacts
4. **Multi-agent specialization** — coding/math/retrieval/planning agents collaborate across nodes
5. **Effective unbounded context** — local + Mem0 + cross-mesh shared retrieval

Frontier closed models implement (1) internally as "extended thinking" and (4) as multi-tool orchestration; they don't have access to (3) or to truly persistent (5) per-user. **OCM's mesh exposes all five as architectural primitives.** This suite tests whether each, alone and in combination, delivers measurable quality lift at acceptable cost.

## 2. Suite-level outcome metrics

Each sandbox has its own `expected.json`, but the suite as a whole reports against three top-level metrics:

| Metric | Target | Refute below | Method |
|---|---|---|---|
| **Quality vs frontier** (battery_avg_pct relative to Claude Opus 4.7) | ≥95% | <85% | Sandbox A |
| **Per-user compute share** (Mac-Mini-minutes per query, amortized) | ≤0.5 | >1.0 | Sandboxes A-C, all measure compute |
| **Mesh-only-possible quality lift** (delta vs single-machine OCM baseline) | ≥+15pp on at least 3 of 5 sandboxes | <+5pp on majority | Sandboxes B, C, D, E |

If all three suite-level metrics confirm, the load-bearing strong claim ("mesh-augmented OCM beats single-machine frontier-class at sub-Mac-Mini per-user cost on specific task classes") is proven on Brand's own hardware, with reproducible artifacts.

---

## 3. Sandbox A — Frontier comparison battery

**Purpose:** The headline benchmark. Compare full mesh-augmented OCM stack head-to-head with Claude Opus 4.7 across a 6-task quality battery.

**Path:** `bench/combination/frontier-comparison-battery/`

**`expected.json`:**
```json
{
  "hypothesis_id": "mesh-vs-frontier-quality-battery",
  "claim": "OCM mesh-augmented Llama 3.1 8B with skill compilation + test-time N=5 + tiered routing matches or exceeds Claude Opus 4.7 on a 6-task battery (MMLU subset, GSM8K, HumanEval, BFCL v3, LongMemEval, GAIA-subset) at sub-Mac-Mini per-user compute",
  "metric": "battery_avg_pct_relative_to_anchor",
  "thresholds": {"confirm_at_least": 95.0, "refute_below": 85.0},
  "comparison_anchor": "claude-opus-4-7-via-anthropic-api",
  "secondary_metric": "user_compute_share_macmini_minutes_p50",
  "secondary_thresholds": {"confirm_at_most": 0.5, "refute_above": 1.0},
  "workload": "frontier-comparison-battery-v1.jsonl",
  "timeout_seconds": 14400,
  "tasks_in_battery": [
    {"name": "MMLU-redux-100q", "weight": 0.15},
    {"name": "GSM8K-100q", "weight": 0.15},
    {"name": "HumanEval-50p", "weight": 0.15},
    {"name": "BFCL-v3-100tools", "weight": 0.20},
    {"name": "LongMemEval-50conv", "weight": 0.15},
    {"name": "GAIA-subset-25q", "weight": 0.20}
  ]
}
```

**OCM stack under test:**
- Local: Llama 3.1 8B Q4 via vLLM with EAGLE-3 + RadixAttention
- Mesh: 5 nodes participating
- Test-time scaling: N=5 best-of-N sampling distributed
- Tiered router: queries scored by difficulty heuristic; ≥0.7 difficulty → borrow Qwen3-30B-A3B from a contributor node
- Skill federation: pre-compiled DSPy GEPA skills loaded for: tool-call extraction, math reasoning, code generation, memory retrieval
- Memory: Mem0 v3 + OpenMemory MCP local-first

**Workload construction:**
| Component | Source | Sample size | Notes |
|---|---|---|---|
| MMLU-redux-100q | EleutherAI lm-evaluation-harness | 100 questions | Stratified subset across 4 categories |
| GSM8K-100q | Public GSM8K | 100 questions | First 100 of test set |
| HumanEval-50p | OpenAI HumanEval | 50 problems | First 50 of test set |
| BFCL-v3-100tools | Berkeley Function Calling Leaderboard v3 | 100 tool-call cases | Across simple/multiple/parallel tool categories |
| LongMemEval-50conv | LongMemEval public dataset | 50 conversations | Multi-session memory recall |
| GAIA-subset-25q | GAIA validation set | 25 questions | Level 1-2 only (Level 3 too hard for 8B class) |

**Per-query measurement:**
- OCM mesh-augmented: full pipeline (router → tiered model → test-time N=5 → reconcile)
- Claude Opus 4.7 anchor: single API call with default settings
- For each: record correctness, wall-clock latency, total compute (mesh: sum of node-seconds; Opus: estimated token-cost equivalent)

**Verdict logic:**
- Compute battery_avg_pct = (mesh_correct / opus_correct) × 100, weighted per task
- Compute user_compute_share = (sum of mesh node-minutes for query) / (total queries × node count) — gives "average Mac-minutes per user-query"
- CONFIRMED if both metrics hit thresholds; REFUTED if either fails its refute threshold; INCONCLUSIVE between

**Decision rule on outcome:**
| Outcome | OCM strategic move |
|---|---|
| CONFIRMED on both | Update README + website hero: "match frontier-class quality on common tasks at sub-Mac-Mini per-user cost." This is the moonshot landing. |
| Quality CONFIRMED, cost REFUTED | Quality story works; revisit mesh efficiency optimizations before user-facing claims |
| Quality REFUTED, cost CONFIRMED | Mesh saves money but doesn't match frontier; reposition around cost + privacy not quality |
| Both REFUTED | Mesh-as-frontier-alternative thesis fails; positioning stays on "free + private + good-enough" |

**Risks / caveats:**
- API cost for Claude Opus 4.7 anchor calls (~$30-100 for full battery)
- GAIA-subset is hard for 8B-class; expect Opus to win this category outright; battery weights account for this
- Skill compilation needed before run; 4 skills × ~100 GEPA rollouts = ~$50-100 in API cost (or use local model for compilation, slower)
- Mesh of 5 contributor nodes needed; this gates the sandbox until at least 5 contributors are online

---

## 4. Sandbox B — Distributed test-time scaling lift

**Purpose:** Isolates mechanism (1) — does distributing best-of-N sampling across nodes deliver measurable quality lift on hard reasoning?

**Path:** `bench/combination/distributed-test-time-scaling/`

**`expected.json`:**
```json
{
  "hypothesis_id": "distributed-test-time-scaling-lift",
  "claim": "Distributing N=5 best-of-N samples across 5 mesh nodes for Llama 3.1 8B Q4 produces >=+10pp accuracy lift on AIME-2024 vs single-node N=1, at no more than 20% wall-clock latency increase",
  "metric": "aime2024_accuracy_pct_delta_vs_n1_baseline",
  "thresholds": {"confirm_at_least": 10.0, "refute_below": 3.0},
  "secondary_metric": "wall_clock_seconds_pct_increase_vs_n1",
  "secondary_thresholds": {"confirm_at_most": 20.0, "refute_above": 50.0},
  "workload": "aime-2024-30q.jsonl",
  "timeout_seconds": 7200,
  "source_for_claim": "Test-Time RL paper (Qwen2.5-Math-7B +159% pass@1 on AIME-2024 with unlabeled test data) — testing mesh-distributed variant"
}
```

**Mechanism under test:**
- Baseline: single Mac Mini, Llama 3.1 8B Q4, N=1, default temperature
- Test: 5 Mac Minis, Llama 3.1 8B Q4 each, N=5 (one sample per node), majority-vote reconciliation
- Reconciliation: simple majority vote on final answer; if no majority, return the answer with highest log-likelihood

**Workload:**
- AIME 2024 — 30 questions (full year's set)
- Why AIME: math reasoning is where test-time scaling shows biggest lift in published evidence
- Reproducibility: AIME 2024 is fully public; reproducible across hardware classes

**Per-query measurement:**
- Baseline N=1: time-to-final-answer on single node
- N=5 distributed: dispatch 5 parallel queries, wait for all, reconcile; record max wall-clock + total compute
- Quality: AIME has correct answers; binary correct/incorrect per problem

**Verdict logic:**
- accuracy_lift_pp = mean(N5_correctness) − mean(N1_correctness) in percentage points
- wall_clock_increase = (N5_p50_seconds − N1_p50_seconds) / N1_p50_seconds × 100
- CONFIRMED if accuracy_lift ≥10pp AND wall_clock_increase ≤20%
- REFUTED if accuracy_lift <3pp OR wall_clock_increase >50%

**Decision rule:**
| Outcome | OCM action |
|---|---|
| CONFIRMED | Lock distributed test-time scaling as a v2 feature; document the +10pp lift as a measured user benefit |
| INCONCLUSIVE (3-10pp lift) | Keep as opt-in feature; user controls the speed/quality tradeoff |
| REFUTED | Mesh test-time scaling doesn't deliver as expected; investigate whether 8B simply can't benefit from N=5 reconciliation |

**Variations to run after baseline confirms:**
- Verifier-guided N=5 (use a different model as verifier instead of majority vote) — expect bigger lift
- Self-consistency with chain-of-thought — expect bigger lift on AIME specifically
- Latent-Trajectory Early Accept (cited from Premai blog) — expect 48-70% token savings vs vanilla N=5

---

## 5. Sandbox C — Tiered routing economics

**Purpose:** Isolates mechanism (2) — does smart difficulty routing deliver near-frontier quality at fractional compute?

**Path:** `bench/combination/tiered-routing-economics/`

**`expected.json`:**
```json
{
  "hypothesis_id": "tiered-routing-economics",
  "claim": "OCM tiered router (easy queries -> local Llama 3.1 8B, hard queries -> borrowed Qwen3-30B-A3B from a mesh contributor) on a 1000-query mixed-difficulty agent workload achieves >=90% of pure-30B-A3B quality at <=30% of pure-30B-A3B compute cost",
  "metric": "quality_pct_of_pure_30b",
  "thresholds": {"confirm_at_least": 90.0, "refute_below": 75.0},
  "secondary_metric": "compute_pct_of_pure_30b",
  "secondary_thresholds": {"confirm_at_most": 30.0, "refute_above": 50.0},
  "workload": "agent-tasks-mixed-difficulty-1000q.jsonl",
  "timeout_seconds": 14400,
  "decision_rule": "If quality is within 90% of pure-30B at <=30% cost, the tiered router is the v1 default. If quality is below 75% or cost exceeds 50%, the router heuristic needs work."
}
```

**Mechanism under test:**
- Baseline (denominator): every query runs on Qwen3-30B-A3B (frontier-quality reference for OCM)
- Test (numerator): every query runs through the tiered router:
  - Difficulty score 0.0-0.3: local Llama 3.1 8B Q4 (cheap, fast)
  - Difficulty score 0.3-0.7: local Llama 3.1 8B Q4 with chain-of-thought (slightly more expensive)
  - Difficulty score 0.7-1.0: borrow Qwen3-30B-A3B from a contributor node
- Difficulty scoring: lightweight classifier trained on labeled difficulty samples (~500 examples); runs in <50ms per query

**Workload:**
- 1000 queries spanning easy (general knowledge, simple code completion) → hard (multi-step reasoning, complex tool use)
- Distribution: 60% easy, 25% medium, 15% hard (matches realistic agent traffic per industry reports)
- Sources: BFCL v3, GSM8K, HumanEval-easy, LongMemEval simple recall, GAIA Level 1, mixed

**Per-query measurement:**
- Both pipelines run all 1000 queries
- Quality: task-specific scoring (correctness for math, pass-rate for code, recall for memory, etc.)
- Compute: track wall-clock per query, total node-seconds across whichever node served the query

**Verdict logic:**
- quality_pct_of_pure_30b = (router_avg_quality / pure_30b_avg_quality) × 100
- compute_pct_of_pure_30b = (router_total_node_seconds / pure_30b_total_node_seconds) × 100
- CONFIRMED if quality ≥90% AND compute ≤30%
- The win condition is NOT 100% quality at 30% cost — it's "near-frontier quality at fraction of compute"

**Decision rule:**
| Outcome | OCM action |
|---|---|
| CONFIRMED | Tiered router becomes v1 default; document 70% compute savings vs all-30B baseline |
| Quality CONFIRMED, cost REFUTED | Router catches difficulty correctly but doesn't save enough compute; tighter difficulty thresholds |
| Quality REFUTED | Router misjudges hard queries; needs better classifier or a third tier (chain-of-thought + 30B borrowing) |
| Both REFUTED | Tiered routing doesn't pay off on this workload; revisit query distribution assumptions |

**Risks / caveats:**
- Difficulty classifier itself is a small ML model; needs training data
- "Borrow Qwen3-30B-A3B from contributor" requires v2+ mesh; v1 simulates by running both models on Brand's own hardware
- Workload distribution (60/25/15) matters; sensitivity analysis required (re-run with 80/15/5 and 40/35/25 distributions)

---

## 6. Sandbox D — Skill federation cross-mesh quality

**Purpose:** Isolates mechanism (3) — do compiled DSPy GEPA skills transfer across nodes without quality loss, and how much do they exceed uncompiled baseline?

**Path:** `bench/combination/skill-federation-cross-mesh/`

**`expected.json`:**
```json
{
  "hypothesis_id": "skill-federation-cross-mesh-quality",
  "claim": "A DSPy GEPA-compiled skill for entity extraction, compiled on Node A with its local Llama 3.1 8B Q4 and transferred via program.save/program.load to Node B's Llama 3.1 8B Q4, reproduces accuracy within 2pp of in-process compilation; net quality vs uncompiled baseline is >=+15pp",
  "metric": "skill_accuracy_pct",
  "thresholds": {"confirm_at_least_vs_uncompiled_pp": 15.0, "confirm_at_most_cross_node_drift_pp": 2.0, "refute_below_vs_uncompiled_pp": 5.0, "refute_above_cross_node_drift_pp": 5.0},
  "workload": "entity-extraction-200samples.jsonl",
  "timeout_seconds": 7200,
  "source_for_claim": "DSPy GEPA paper (arxiv 2507.19457): GPT-4.1-Mini 46.6 -> 56.6 on AIME-2025; Gemini 2.5 Flash Lite 80.7 -> 97.8 on M&A entity extraction"
}
```

**Mechanism under test:**
1. Compile DSPy GEPA program on Node A with Llama 3.1 8B Q4 + 100 labeled entity-extraction examples
2. Save artifact via `program.save("/skills/entity-extract.json")`
3. Transfer to Node B (different Mac Mini, same model + quantization but different hardware)
4. Load via `program.load("/skills/entity-extract.json")` on Node B
5. Run held-out 200 entity-extraction test samples on three configurations:
   a. Uncompiled Llama 3.1 8B Q4 baseline
   b. In-process compiled (Node A: compile and run)
   c. Cross-mesh (Node A compile, Node B run)

**Workload:**
- 200 entity-extraction samples
- Format: conversational text → required entity tuples (person, place, date, relation)
- Train: 100 labeled samples used for GEPA compilation
- Test: 200 held-out samples for evaluation
- Source: synthesized from public dialog corpora + manual annotation (one-time effort)

**Per-query measurement:**
- Run all 200 test samples through each of the three configurations
- Score: F1 on extracted entities (precision + recall)
- Record per-sample latency and total compute

**Verdict logic:**
- net_lift_pp = (cross_mesh_F1 − uncompiled_F1) × 100
- cross_node_drift_pp = abs(in_process_F1 − cross_mesh_F1) × 100
- CONFIRMED if net_lift ≥15pp AND drift ≤2pp
- REFUTED if net_lift <5pp OR drift >5pp

**Decision rule:**
| Outcome | OCM action |
|---|---|
| CONFIRMED | Skill federation thesis confirmed; commit to v2+ skill marketplace architecture; this is the network-effect lever validated |
| Quality lift CONFIRMED, drift REFUTED | Skills work but don't transfer cleanly; need per-machine recompilation or hardware-aware compilation |
| Quality lift REFUTED | DSPy GEPA doesn't deliver promised lift on this task; revisit whether OCM's skill-federation thesis holds for general tasks |
| Both REFUTED | Network-effect thesis breaks; v2+ strategy needs a new differentiator |

**Risks / caveats:**
- DSPy GEPA compile time is non-trivial (~30-60 min for a 100-sample compile); needs strong compute budget
- Hardware drift could be small but real if quantization or kernel choices differ subtly between Mac Mini variants
- Need 2 actual Mac Minis (or M-series machines) — not just simulated

**Stretch goals beyond baseline:**
- Test on 5 different skills (entity extraction, conversation summarization, tool selection, math step extraction, code refactor identification) — broader thesis confirmation
- Test cross-architecture transfer (compile on Mac Metal, run on NVIDIA CUDA) — hardest case
- Test signature persistence (does a skill compiled on Llama 3.1 8B work on Qwen3 8B?) — important for the marketplace economics

---

## 7. Sandbox E — Effective context via mesh retrieval

**Purpose:** Isolates mechanism (5) — does Mem0 + cross-mesh retrieval match or exceed frontier 1M-context model performance on long-context tasks?

**Path:** `bench/combination/effective-context-via-mesh-retrieval/`

**`expected.json`:**
```json
{
  "hypothesis_id": "effective-context-via-mesh-retrieval",
  "claim": "OCM Llama 3.1 8B Q4 (32K native context) with Mem0 v3 + Aider repomap + cross-mesh shared retrieval matches or comes within 2pp of Claude Opus 4.7 (1M context) on Stanford MemoryArena multi-session interdependent tasks",
  "metric": "memoryarena_pct",
  "thresholds": {"confirm_at_least_vs_frontier_pp": -2.0, "refute_below_vs_frontier_pp": -10.0},
  "comparison_anchor": "claude-opus-4-7-via-anthropic-api",
  "workload": "memoryarena-multisession-extended-100conv.jsonl",
  "timeout_seconds": 14400,
  "secondary_metric": "user_compute_share_macmini_minutes_p50",
  "secondary_thresholds": {"confirm_at_most": 0.5, "refute_above": 1.0}
}
```

**Mechanism under test:**
- Local: Llama 3.1 8B Q4 with 32K native context
- Mem0 v3 + OpenMemory MCP for episodic memory
- Aider-style repomap for compressed views of accumulated conversation history
- Cross-mesh shared corpus (simulated — single-node retrieval over a "synthetic mesh memory" of 10× the local memory)
- Total effective searchable corpus: 100M+ tokens (vs Claude's 1M context window)
- Anchor: Claude Opus 4.7 with full 1M context (everything stuffed in)

**Workload:**
- 100 conversations from MemoryArena multi-session extended
- Each conversation: 5-10 sessions, with interdependent tasks across sessions
- Questions probe the agent's ability to recall, integrate, and reason across multiple prior sessions

**Per-query measurement:**
- For each of 100 conversations:
  - Run Claude Opus 4.7 with full conversation history in 1M context (anchor)
  - Run OCM stack with retrieval-bounded 32K (test)
- Score: task completion correctness per MemoryArena's published rubric
- Compute: full mesh node-seconds for OCM; estimated tokens × pricing for Opus

**Verdict logic:**
- frontier_delta_pp = (ocm_avg_pct − opus_avg_pct) × 100
- CONFIRMED if delta ≥-2pp (within 2 percentage points) AND OCM compute ≤0.5 Mac-Mini-minutes
- REFUTED if delta <-10pp (significantly worse) OR compute >1.0 Mac-Mini-minutes

**Decision rule:**
| Outcome | OCM action |
|---|---|
| CONFIRMED | Effective context via retrieval is OCM's structural advantage at long-context; document this as a key user-facing claim |
| Within 5pp of frontier | Strong but not dominant; document with appropriate hedging |
| 5-10pp behind | Useful but not frontier-class; revisit retrieval pipeline |
| >10pp behind | Mem0 + retrieval doesn't match true 1M-context; need to investigate whether retrieval misses context-critical pieces |

**Risks / caveats:**
- MemoryArena dataset availability needs verification (Stanford 2026 release status)
- Claude Opus 4.7 1M-context usage is expensive (~$5-15 per conversation × 100 conversations = $500-1500)
- "Cross-mesh shared corpus" is simulated for v1 sandbox; real federation tested only post-v2

---

## 8. The mesh-only-possible quality lift metric

The five sandboxes also report a unified "mesh advantage" metric: the delta between mesh-augmented OCM and pure single-machine OCM (no test-time scaling, no tiered routing, no skill federation, no mesh retrieval). This isolates the question: **how much of the win comes from the mesh specifically, vs. just having good local components?**

| Sandbox | Single-machine OCM baseline | Mesh-augmented OCM | Mesh-only lift target |
|---|---|---|---|
| A | Llama 8B + Mem0 (no test-time, no router) | Full mesh stack | ≥+15pp battery_avg |
| B | N=1 single node | N=5 distributed | ≥+10pp on AIME |
| C | Llama 8B every query | Tiered router with 30B borrowing | ≥+8pp avg quality |
| D | Uncompiled Llama 8B | Cross-mesh compiled skill | ≥+15pp on extraction |
| E | Llama 8B + local Mem0 only | + cross-mesh shared retrieval | ≥+5pp on MemoryArena |

If at least 3 of these 5 confirm their ≥mesh-only lift threshold, the structural advantage of the mesh is empirically validated, distinct from "OCM happens to use good components."

---

## 9. Hardware + budget needed to run the suite

**Minimum viable run (OCM v1 with simulated mesh):**
- 1 RTX 4090 + Llama 3.1 8B Q4 + Qwen3-30B-A3B Q4 (both pre-cached)
- 2-3 Mac Minis (M2/M3/M4 base or higher) acting as separate "mesh nodes"
- Total hardware cost if self-funded: ~$3-5K
- Estimated wall-clock to run full suite: ~40-80 hours (mostly in Sandbox A and E with API anchor calls)
- Estimated API budget for Claude Opus 4.7 anchors: $600-1800 across all sandboxes

**Production-grade run (after viable beta tier):**
- 5+ contributor nodes online (the 3 high + 2 mid configuration from contributor-sizing math)
- Full mesh transport via libp2p/iroh
- Reproducible across hardware classes via the bench framework's hardware-class tagging
- Wall-clock: ~24-48 hours (parallel across nodes)
- API budget: same as above — frontier anchor calls don't change

**Pre-bench prep work:**
1. Workload assembly (~16-32 hours): compile MMLU-redux, GSM8K, HumanEval, BFCL, LongMemEval, GAIA-subset into a single battery JSONL
2. DSPy GEPA skill compilation (~10-20 hours of compute + $50-100 API): pre-compile the 4 skills used in Sandbox A
3. Difficulty classifier training (~4-8 hours): label 500 queries by difficulty, train a small classifier
4. Synthetic entity-extraction dataset (~8-16 hours of human annotation): for Sandbox D
5. MemoryArena dataset acquisition (~variable): depends on Stanford release status

**Total prep + run budget:** ~120-200 hours of human time + ~$1000-2500 API spend + 2-5 contributor nodes online for ~1 week.

---

## 10. Decision matrix — what each combined outcome means for OCM

The five sandboxes give OCM 32 possible outcome combinations (2^5). The strategically meaningful outcomes:

| Pattern | OCM strategic position |
|---|---|
| **All 5 CONFIRM** | The "compete on quality" thesis is proven. Position OCM as a frontier alternative for specialized + repeated workloads. Update website hero, README, all marketing accordingly. This is the moonshot landing. |
| **A, B, D CONFIRM; C, E mixed** | Skill federation + test-time scaling are the differentiators; routing and retrieval need more engineering. Lock A/B/D as locked spec; iterate on C/E. |
| **A REFUTED, B-E mostly CONFIRM** | Mesh delivers component-level wins but doesn't aggregate to frontier-equivalent quality. Position remains "good alternative, not frontier replacement." |
| **B, C CONFIRM; A, D, E mixed/refuted** | Compute efficiency wins (test-time + routing); quality wins less so. Position around "near-frontier at sub-frontier cost." |
| **B, D, E CONFIRM; A, C refuted** | Mesh wins on specialization + persistence + context, not aggregate. Lean into "the mesh agent that remembers and specializes." |
| **All 5 REFUTED** | Mesh thesis as a quality lever fails. Reposition entirely around free + private + good-enough. Honest fallback. |

This matrix should drive concrete website copy, README claims, and pitch language depending on what we measure. **No outcome triggers "fake the numbers."** Every position above is honest and supportable with the data.

---

## 11. Implementation priority order

When the bench framework scaffold lands (Track C of master operations plan), implement these sandboxes in order:

1. **Sandbox B (distributed test-time scaling)** — fastest to set up; isolates one mechanism cleanly; provides early evidence
2. **Sandbox D (skill federation transfer)** — validates the network-effect lever; medium setup cost
3. **Sandbox C (tiered routing)** — validates the per-query economics; needs difficulty classifier
4. **Sandbox E (effective context)** — needs MemoryArena access + Claude Opus anchor budget
5. **Sandbox A (frontier comparison battery)** — most expensive; gates on first 4 working; the moonshot evidence

Each prior sandbox de-risks the next. Sandbox A only makes sense to run once B-E individually establish their mechanisms work.

---

## 12. The honest framing OCM should adopt

Whatever the outcomes, OCM's marketing posture should be:

- **NOT** "we beat closed AI on every benchmark"
- **NOT** "frontier-class quality on a single Mac Mini"
- **NOT** "free GPT-5 alternative"

Instead:

- **YES** "for any task that benefits from specialization, repetition, or long-running context, the mesh structurally wins"
- **YES** "we measure every claim against frontier closed models, with reproducible code anyone can re-run"
- **YES** "the mesh delivers near-frontier quality at sub-Mac-Mini per-user cost on benchmarked task classes"
- **YES** "the open thing competes with the closed thing on the dimensions that matter to most users — privacy, persistence, cost, control"

This framing sets honest expectations and is defensible against scrutiny. The benchmark suite proves what we can claim; we don't claim what the benchmarks don't support.

---

## Sources backing this plan

- **Test-time scaling lift baselines:**
  - [Test-Time RL boosts Qwen-2.5-Math-7B +159% on AIME 2024](https://huggingface.co/blog/aufklarer/ai-trends-2026-test-time-reasoning-reflective-agen)
  - [Latent-Trajectory Early Accept (Premai blog)](https://blog.premai.io/speculative-decoding-2-3x-faster-llm-inference-2026/)
- **DSPy GEPA quality lift:**
  - [GEPA: Reflective Prompt Evolution Outperforms RL (arxiv 2507.19457, ICLR'26 Oral)](https://arxiv.org/abs/2507.19457)
  - [DSPy program.save/load API](https://dspy.ai/api/optimizers/GEPA/overview/)
- **MemoryArena agentic memory test:**
  - [MemoryArena (arxiv 2602.16313, Stanford 2026)](https://arxiv.org/abs/2602.16313)
  - [MemoryArena project page](https://memoryarena.github.io/)
- **Tiered routing precedents:**
  - [Microsoft Agent Framework CodeAct: 50% latency cut, 60% token cut](https://devblogs.microsoft.com/agent-framework/codeact-with-hyperlight/)
  - [Smolagents: 30% fewer steps, 30% fewer LLM calls](https://github.com/huggingface/smolagents)
- **Effective-context patterns:**
  - [Aider repomap mechanism](https://aider.chat/docs/repomap.html)
  - [Continue.dev hybrid retrieval blueprint](https://lancedb.com/blog/the-future-of-ai-native-development-is-local-inside-continues-lancedb-powered-evolution/)
  - [Mem0 v3 token-efficient memory algorithm](https://mem0.ai/blog/mem0-the-token-efficient-memory-algorithm)

---

This plan is the bridge from "interesting mesh thesis" to "measured, defensible, frontier-comparable claims." Five sandboxes, one suite, a clean decision matrix. When the bench framework scaffold lands, this is the highest-leverage thing to run.
