# Memory-Driven Sub-Context Retrieval — Deep Dive

**Date:** 2026-05-09
**Author:** OCM research stream
**Scope:** Survey of agentic context retrieval / sub-context lookup / memory-as-a-tool patterns, with a specific lens on what works for small (7-13B) open-source models and what could federate across an OCM-style mesh.
**Methodology:** WebFetch + WebSearch over project READMEs, papers, vendor docs, third-party benchmarks. Every load-bearing claim is cited. "I don't know" is preferred over speculation.
**Companion to:** [`2026-05-08-agent-memory-orchestration.md`](./2026-05-08-agent-memory-orchestration.md), which evaluated Letta vs Mem0 vs Zep at the *memory-layer* level. This report goes deeper into the broader **retrieval-pattern** landscape.

---

## 1. Taxonomy of approaches

The pattern space "agent has a small working context, fetches more on demand" splits into seven mostly-orthogonal axes. The same project can sit at different points on each axis.

| Pattern | Mechanism | Who's doing it | Where the LLM intelligence sits |
|---|---|---|---|
| **Tool-driven memory** | Agent decides when to call `archival_memory_search()`, `recall_memory()`, etc. | Letta (formerly MemGPT), Claude Code's Memory MCP servers, MemGPT-derived projects. | At runtime: the agent itself drives retrieval. |
| **Library-driven retrieval** | Library auto-retrieves before agent runs; agent receives pre-fetched chunks. | Mem0, Mem0's OpenMemory MCP, plain-RAG patterns. | At ingest: extraction quality matters; runtime is dumber. |
| **Hierarchical/Tiered memory** | Short-term → mid-term → long-term, with promotion rules. | Letta (core/recall/archival), MemoryOS (EMNLP 2025 Oral), Cognee (session→graph fallthrough). | Distributed across tiers; promotion logic is heuristic. |
| **Knowledge-graph retrieval** | Triples/entities pre-extracted; query traverses graph. | Microsoft GraphRAG, LightRAG, PathRAG, HippoRAG/HippoRAG2, Graphiti (bi-temporal), Cognee. | At ingest: needs LLM strong enough to extract entities. |
| **Compressed-context view** | Single compact representation of corpus optimized for LLM context. | Aider repomap, Repomix `--compress`, Augment Context Engine. | Heuristic — graph ranking + tree-sitter, not LLM-driven. |
| **Just-in-time fetch** | Agent reads files / explores incrementally rather than indexing. | Cline, Claude Code (sequential reads + grep), Aider in non-mapped mode. | At runtime: agent does the exploration as a planning step. |
| **Skill compilation** | Compiled programs that *learn* the right retrieval strategy per task. | DSPy GEPA, Stanford-led OSS. | Offline at compile time, frozen at runtime. |

A useful clarification: **"library-driven" vs "tool-driven"** is the most consequential axis for OCM's small-model thesis. In tool-driven retrieval, the model has to *decide* to retrieve. In library-driven retrieval, retrieval is run unconditionally and the chunks are injected. Letta's own engineers conceded that small models like Llama 8B can't reliably maintain a conversation alongside tool calls — that's a tool-driven failure mode, and Mem0 sidesteps it by being library-driven by default.[^letta-blog][^why-small-llms-fail]

A second clarification: **knowledge graphs are not free.** A graph is only useful if entities and relations are extracted accurately. Cognee's own documentation (verified against their Ollama setup guide) explicitly recommends **deepseek-r1:32b or Llama3.3-70b** and warns that 8B-class models "often produce noisy graphs" with hallucination polluting nodes and edges.[^cognee-ollama] That's a hard constraint on small-model deployments and disqualifies "GraphRAG via local-only Llama 8B" as a default for OCM v1.

### 1.1 The cross-cutting result that should change priors

The ICLR 2026 paper "When to use Graphs in RAG: A Comprehensive Analysis" (with the open-source GraphRAG-Bench) is the most useful evidence in this whole space, because it pits the methods against each other on the same workloads:[^graphrag-bench-paper]

| Task class | Best vector RAG | Best GraphRAG | Winner |
|---|---|---|---|
| Fact retrieval (novel dataset) | 60.92% | 60.14% | **Vector RAG** |
| Complex multi-hop reasoning | 42.93% | 53.38% (HippoRAG2) | **GraphRAG** |
| Summarization | 51.30% | 64.40% (MS-GraphRAG) | **GraphRAG** |
| Medical fact retrieval | 64.73% | 66.28% (HippoRAG2) | tie / slight GraphRAG |

The honest verdict: **graph approaches are not categorically better than vector RAG.** They win when the task requires bridging multiple concepts; they tie or lose for direct fact retrieval. For OCM, this means a single-aircraft "smart RAG" architecture should be **vector-first with graph as an optional escalation path**, not graph-by-default.

---

## 2. Top OSS projects in the space (with hard data)

| Project | Stars | Latest | License | Lang | OCM fit |
|---|---|---|---|---|---|
| **Mem0** | 55.2k | v3.0.2 (May 7 2026) | Apache 2.0 | Python/TS | **HIGH (already locked)** |
| **Letta** | 22.5k | v0.16.7 (Mar 31 2026) | Apache 2.0 | Python | **LOW (small-model risk)** |
| **Graphiti (Zep core)** | 25.8k | v0.29.0 (Apr 27 2026) | Apache 2.0 | Python | **MEDIUM (v2+ candidate)** |
| **Cognee** | 17.1k | v1.0.9 (May 8 2026) | Apache 2.0 | Python | **LOW (32B+ minimum, blocks 8B users)** |
| **Microsoft GraphRAG** | 32.9k | v3.0.9 (Apr 13 2026) | MIT | Python | **LOW (indexing cost flagged in own README)** |
| **LightRAG** | 34.9k | v1.4.16 (May 7 2026) | MIT | Python | **MEDIUM (cheaper graph option)** |
| **PathRAG** | (research code) | Feb 2025 paper | research code | Python | **WATCH (not production-ready)** |
| **HippoRAG / HippoRAG2** | published research | ICML 2025 | research code | Python | **WATCH** |
| **R2R** | 7.8k | active | MIT | Python | **MEDIUM (RAG-as-service, productized)** |
| **Verba** | 7.2k | active | BSD 3-Clause* | Python | **LOW (Weaviate-coupled)** |
| **dsRAG** | 1.6k | active | MIT | Python | **MEDIUM (FinanceBench: 96.6% vs 32% vanilla)** |
| **LlamaIndex** | (very large) | active | MIT | Python | **HIGH for primitives (HierarchicalNodeParser, AutoMergingRetriever)** |
| **MemoryScope / ReMe** (Alibaba) | small | v0.1.8 (Sept 2025) | Apache 2.0 | Python | **LOW (less momentum than Mem0)** |
| **MemoryOS** | EMNLP 2025 Oral | research code | research code | Python | **WATCH (+49% F1 LoCoMo)** |
| **A-MEM** | NeurIPS 2025 | research code | research code | Python | **WATCH (Zettelkasten dynamic notes)** |
| **Aider repomap** (in Aider) | 30k+ | active | Apache 2.0 | Python | **HIGH (pattern: portable PageRank + tree-sitter)** |
| **Repomix** | 22.4k | active | MIT | TS | **HIGH (tree-sitter --compress = ~70% token cut)** |
| **Continue.dev** | 33k+ | active | Apache 2.0 | TS | **HIGH (hybrid LanceDB + ripgrep + LLM rerank pattern)** |
| **Augment Context Engine** | (closed) | — | proprietary | — | **PATTERN ONLY** |
| **Sourcegraph Cody** | (open snapshot) | discontinued Free July 2025 | Apache 2.0 | TS | **LOW (no longer maintained for individuals)** |
| **Cline** | very large | active | Apache 2.0 | TS | **MEDIUM (no-index philosophy is contrarian)** |
| **Roo Code** | active | active | Apache 2.0 | TS | **MEDIUM (HNSW + AST chunking)** |

*Verba license needs direct verification — copyright header is Weaviate B.V.; the LICENSE file wasn't fully retrieved during research.

### 2.1 The Mem0 confidence-check

**The Mem0 pick is CONFIRMED.** Three pieces of new evidence reinforce it beyond what the prior memory-orchestration report had:

1. **Mem0 v3 hits 91.6 on LoCoMo, 93.4 on LongMemEval, ~7000 tokens per retrieval.**[^mem0-token-efficient] The +26 LongMemEval claim resolved as **67.8 → 93.4**, not 85% as some derivative blog posts reported. This is a real algorithmic upgrade, not marketing.
2. **OpenMemory MCP** is Mem0's local-first surface — Docker + Postgres + Qdrant, supports Ollama, no cloud sync. That's exactly what OCM needs for v1 single-node deployment.[^openmemory-mcp]
3. **Mem0 is library-driven by default.** The basic usage example shows developers explicitly calling `memory.search()` to fetch chunks before passing to the LLM — the agent is not required to drive its own memory tools.[^mem0-readme] That's the directly small-model-aligned pattern.

The dissenting evidence is **Letta's filesystem benchmark** (74.0% LoCoMo with GPT-4o-mini "tool rules"), where Letta argues plain filesystem tools beat specialized memory.[^letta-filesystem] But Letta themselves call this "apples to oranges" because the harness differs. Mem0's 93.4 on LongMemEval is on a published, reproducible benchmark with code released. **Net: Mem0 wins both apples and oranges.**

### 2.2 Letta — confirm the de-prioritization

Letta's filesystem benchmark is interesting but does not rescue the framework as a small-model fit. Their own engineers told us Llama 8B can't drive their tool paradigm reliably; the GPT-4o-mini result requires "tool rules" to make the model "only partially autonomous"[^letta-filesystem] — the same pattern that breaks at smaller scales. **Status: still LOW for OCM v1.** Worth revisiting if Letta ships a "library-driven mode" that doesn't require the model to choose retrieval calls.

### 2.3 Graphiti — same verdict as before, with one nuance

Graphiti's bi-temporal graph remains the most architecturally principled long-term-memory system. **94.8% on DMR, 71.2% on LongMemEval (GPT-4o-mini)**[^zep-paper] is meaningful. But Graphiti is still **a graph engine**, and the GraphRAG-Bench result above tells us graph wins are task-specific. Combined with the Neo4j/FalkorDB/Kuzu install friction, **OCM v1 keeps Graphiti out of the locked stack**, with the addition that v2+ should evaluate it specifically for *complex-reasoning workloads* where the graph advantage is real, not as a general-purpose drop-in.

### 2.4 The under-reported entrants

- **MemoryOS** (EMNLP 2025 Oral) — hierarchical short/mid/long-term with promotion rules; **+49.11% F1 and +46.18% BLEU-1 on LoCoMo**.[^memoryos] Research code, but the architectural pattern is the most disciplined OS-style tiering published in the field.
- **A-MEM** (NeurIPS 2025) — Zettelkasten-style auto-linking notes, evaluated across six foundation models.[^amem] Pattern-instructive even if the implementation is research-grade.
- **dsRAG** — boutique alternative; **96.6% on FinanceBench vs 32% vanilla RAG**.[^dsrag] The win is on document-rich corpora with structure; their secret sauce is their `dsParse` document parser. Worth a sandbox specifically for OCM users with PDF-heavy memories.

---

## 3. Patterns that work for SMALL models (7-13B)

This is the strategic core of OCM's "smaller-models-punch-above-weight" thesis. The evidence is stronger now than it was a year ago, but it's still uneven.

### 3.1 Library-driven retrieval (Mem0 pattern) — STRONG evidence for small models

The reason Mem0 works on small models is structural: the model isn't asked to *decide* to retrieve, it just receives chunks. The hard work is in extraction (which can run async with a stronger model) and in the multi-signal retrieval pipeline (semantic + BM25 + entity match). Llama 8B at runtime only needs to consume retrieved context, not orchestrate retrieval. Mem0's own docs describe a "single-pass ADD-only extraction" pipeline that "cuts extraction latency roughly in half"[^mem0-token-efficient] — they explicitly traded LLM agency for predictability, which is the right tradeoff for OCM.

### 3.2 DSPy GEPA — STRONG evidence on specific tasks

GEPA (ICLR 2026 Oral) achieves +10pp on AIME-2025 with GPT-4.1-Mini, and pushed Gemini 2.5 Flash Lite from 80.7% → 97.8% on M&A entity extraction. Crucially, **DSPy programs are saveable artifacts**: `program.save("path")` / `program.load("path")` is a first-class API.[^dspy-gepa] That's the technical primitive OCM needs to ship "compiled skills" across the mesh. (See Section 4.)

### 3.3 HippoRAG 2 — MEDIUM evidence on small models

HippoRAG 2's headline number (+7% associative memory over SOTA embedding model) is modest and the published experiments emphasize 70B; they list Llama-3.1-8B-Instruct as supported but don't lead with small-model numbers.[^hipporag-paper] The biological-inspiration framing is more interesting than the empirical lift. Treat as "watch list, not adopt."

### 3.4 Cognee — WEAK evidence on small models, by their own admission

Cognee's setup guide for Ollama explicitly recommends ≥32B models and warns 8B "produces noisy graphs" with up to 90% hallucination polluting nodes and edges.[^cognee-ollama] **Honest take: Cognee is not the right small-model knowledge-graph option.** If OCM ever wants graph memory on small hardware, the path is "vector-first, graph escalation only when needed" — and even then, the graph extraction step should run on a stronger borrowed-from-the-mesh model (an actual OCM differentiator at v2+).

### 3.5 Compressed views (Aider repomap, Repomix) — STRONG evidence (different domain)

Aider's repomap uses NetworkX PageRank ranking on a tree-sitter tag graph, fits results into a configurable token budget (1k default) via binary search.[^aider-repomap] Repomix's `--compress` (tree-sitter) cuts tokens by **~70% while preserving structure**.[^repomix] These are *deterministic* approaches — no LLM call needed at retrieval time. They scale down to any model size because the compression happens in pre-processing.

### 3.6 What does NOT work for small models

Tool-driven memory paradigms (Letta-style `archival_memory_search()` calls), graph retrieval that requires the agent to reason over triples, and any pattern where the agent must *plan* a retrieval strategy as part of its loop. The MemoryArena benchmark (Stanford 2026) shows that **agents at near-100% on LoCoMo plummet to 40-60% on multi-session interdependent tasks**[^memoryarena] — a sober reminder that retrieval recall is not the same as agentic memory utilization. OCM should benchmark on MemoryArena specifically, not just LoCoMo.

---

## 4. The federated-memory angle (OCM's network-effect lever)

Has anyone shipped a working federated personal-AI memory system in production? **No, not yet.** The pieces exist; the integration doesn't.

### 4.1 What exists today

- **Flower** (FedAI Labs) is the canonical OSS federated learning framework, used in academic research broadly. It's machine-learning-framework-agnostic (PyTorch, TF, HuggingFace, MLX, etc.).[^flower]
- **MIT FTTE** (arxiv 2510.03165, paper accompanying MIT News April 29, 2026) is a federated training engine specifically for resource-limited devices: **81% faster training, 80% memory reduction, 69% communication payload reduction**.[^mit-ftte] FTTE proves the device-class OCM targets (Mac Mini, mid-range PC) is feasible for federated learning, not just inference.
- **Agentic-FL** (arxiv 2604.04895) is the most directly OCM-aligned paper: "Language Model-based Agents (LMagents) assume autonomous orchestration roles; the training pipeline is negotiated peer-to-peer."[^agentic-fl] This is functionally identical to OCM's mesh-of-personal-agents thesis. Research-grade only.
- **DSPy GEPA save/load** is the *only* shippable primitive today for "I compiled a skill, you can run it." Compiled programs are deterministic artifacts, easy to checksum, easy to redistribute over the mesh.
- **OpenMemory MCP** (Mem0) is local-first by default — no federation, but the local store is structured, exportable, and could in principle be diffed/synced.

### 4.2 Open research questions for OCM

The hard problems federated memory has to solve are not solved in OSS today:

- **Privacy-preserving memory exchange.** Differential privacy is well-studied for ML training. Applying it to *episodic agent memory* (which contains personally identifying information at high density) is much less explored. The arxiv 2604.16548 "Mnemonic Sovereignty" survey explicitly flags this as an active research frontier, not a solved problem.[^mnemonic-sovereignty]
- **Skill federation vs memory federation.** These are different. Compiled DSPy skills can be redistributed without leaking user data — they're deterministic programs trained on labeled examples a contributor donated. Memory federation (one user's episodic recall benefits another) requires anonymization, attribution, and consent; nobody has shipped this at scale.
- **Sybil resistance for shared knowledge.** If skills/memories are shared across the mesh, an attacker could pollute the shared layer. Bittensor's reputation/staking primitives are partial answers; nothing exists tuned for memory-poisoning specifically.

### 4.3 The cleanest OCM-feasible federation path

**Skill federation, not memory federation, is the v2+ wedge.** Specifically:

1. A contributor compiles a DSPy program for a high-value task (e.g., "summarize a multi-hour conversation into <50 entities for memory ingest").
2. They publish the compiled artifact (signed, checksummed) over the OCM mesh.
3. Other users' agents can opt-in to use the skill by `program.load()`.
4. Reputation/quality is measured per-skill via the bench framework.

This is **OCM's actual network-effect lever**: every contributor's optimization makes the agent layer smarter for everyone, with minimal privacy surface (no user data crosses devices). Memory federation is a v3+ research bet.

---

## 5. The "code-aware sub-context" frontier

Code agents are the most active proving ground for sub-context retrieval, partly because codebases are large, partly because the structure is exploitable. There's a real philosophical split that's instructive for OCM.

### 5.1 The two camps

**Index-everything camp:**
- **Continue.dev `@codebase`** — LanceDB local, transformers.js local embeddings, ripgrep keyword + vector hybrid, LLM rerank.[^continue-codebase] Local-first; nothing leaves the user's machine.
- **Roo Code** — HNSW vector index with AST-aware chunking.[^roo-codebase]
- **Cursor** — closed-source, indexes with embeddings, periodically re-indexes.
- **Augment Context Engine** — closed; claims real-time indexing of 400k+ files; "30-80% quality improvements" across leading agents.[^augment-engine]
- **Sourcegraph Cody** — Apache 2.0 OSS; only Cody Enterprise is maintained as of July 2025.

**Don't-index-just-explore camp:**
- **Cline** — explicitly *no* index; ripgrep + tree-sitter + sequential file reads. Argument: chunks lose coherence, indexes go stale, vectors leak IP. Cline doesn't publish numbers backing the claim — it's a stated design philosophy, not a benchmark.[^cline-no-index]
- **Claude Code** (Anthropic's own) — similar pattern: tools for grep, file read, MCP servers for retrieval; no built-in vector index.
- **Aider** in non-mapped mode — git-aware file editing without persistent index.

**Compressed-view camp (orthogonal):**
- **Aider repomap** — NetworkX PageRank + tree-sitter tags + binary-search to fit token budget. ~1k tokens default; deterministic.[^aider-repomap]
- **Repomix** `--compress` — tree-sitter compression, ~70% token reduction.[^repomix]
- **GitNexus** — tree-sitter knowledge graph served as Graph RAG context; hit #1 on GitHub trending April 2026.[^gitnexus]

### 5.2 What OCM can borrow

Three concrete patterns transfer cleanly to general-purpose agent context:

1. **Compressed views beat both indexing and exploration when the corpus has structure.** Aider's repomap fits a 100k-LoC repo into 1k tokens with PageRank ranking — that's the same problem as "summarize my agent's memory into 1k tokens of working context." The technique generalizes: any corpus with citation/reference structure can be PageRank-ranked.
2. **Hybrid retrieval beats pure vector or pure keyword.** Continue.dev's exact stack (LanceDB + ripgrep + LLM rerank, all local) is the cleanest production pattern for OCM's local-first single-node architecture. Borrow it.
3. **Sequential exploration is a viable fallback.** Cline's no-index philosophy is contrarian but the empirical data (their own product is widely used) suggests it works for sufficiently capable models. For OCM's 7-13B target it's *not* the default — small models lack the planning chops to navigate a corpus blind — but it's a useful "v1.5" mode for users running 30B+ models on the mesh.

### 5.3 Recent paper to track

"Compressing Code Context for LLM-based Issue Resolution" (March 2026, arxiv 2603.28119) introduces Oracle-guided Code Distillation (OCD): genetic search + delta debugging to reduce code contexts to "minimal sufficient subsequences."[^code-context-paper] It's per-task expensive (similar to DSPy GEPA's compile cost), but the *artifact* — a small distilled context — is reusable. This is the "compile a context" pattern, which is interestingly parallel to "compile a skill."

---

## 6. Bottom line for OCM

### 6.1 Mem0 confidence-check: CONFIRMED

The Mem0 pick is reaffirmed with stronger evidence than was available at the prior commit. Mem0 v3 (91.6 LoCoMo, 93.4 LongMemEval, ~7000 tokens/retrieval) is the most defensible memory-layer choice for OCM v1, and OpenMemory MCP gives us the local-first surface we need for the single-node v1 product. Library-driven retrieval is the right architectural fit for the small-model thesis.

The main risks: (a) MemoryArena exposes that LoCoMo near-saturation does *not* mean agentic memory works in practice (40-60% drop on interdependent tasks). OCM should benchmark on MemoryArena, not just LoCoMo. (b) Letta's filesystem-based "agents-with-tools beat specialized memory" claim deserves a sandbox of its own — even though Letta concedes the comparison is unfair, the underlying insight ("filesystem + grep is enough for many users") might apply.

### 6.2 Top 3 sub-context retrieval techniques to integrate into OCM v1

1. **Mem0 v3 with OpenMemory MCP local mode** — locked. Library-driven retrieval, ~7000 tokens/call, ships with Ollama support out of the box.
2. **Aider repomap pattern (PageRank + tree-sitter compressed view) for any structured corpus.** Implement as a generic "compressed-view" tool that OCM exposes for code, docs, conversation logs, anything with reference structure. Token-budget-bounded, deterministic, no LLM call at retrieval time.
3. **Continue.dev hybrid retrieval pattern (LanceDB + ripgrep + LLM rerank, all local)** for code-context tooling. This is the production blueprint to lift wholesale.

### 6.3 Top 3 to integrate into OCM v2+ (mesh era)

1. **DSPy GEPA skill compilation + signed skill artifacts over the mesh.** This is OCM's actual network-effect lever. Skills are deterministic, redistributable, privacy-clean (no user data leaks), and improve every contributor's agent layer.
2. **Graphiti as opt-in for complex-reasoning workloads.** The GraphRAG-Bench data shows graph wins are real for multi-hop reasoning and summarization, but task-specific. Run it where it earns its install cost.
3. **Cross-mesh "borrow stronger model for ingest" pattern.** Use a borrowed 30B+ model from a contributor with VRAM to do entity/graph extraction on memory ingest, then run all retrieval/conversation on the local 7-13B. This sidesteps Cognee's "32B-minimum" trap and is a structural advantage OCM has over single-node products.

### 6.4 Concrete `expected.json` sandbox hypotheses for the bench framework

These slot into the existing bench framework at `bench/isolation/memory-layers/` and `bench/isolation/sub-context-retrieval/`. Format matches `2026-05-08-ocm-bench-framework-plan.md`.

```json
{
  "hypothesis_id": "mem0-v3-llama8b-locomo",
  "claim": "Mem0 v3 single-pass extraction with Llama 3.1 8B Q4 hits >=85% accuracy on LoCoMo with average <=8000 tokens per retrieval call",
  "metric": "locomo_accuracy_pct",
  "thresholds": {"confirm_at_least": 85.0, "refute_below": 75.0},
  "secondary_metric": "avg_retrieval_tokens",
  "secondary_thresholds": {"confirm_at_most": 8000, "refute_above": 12000},
  "workload": "locomo-full.jsonl",
  "source_for_claim": "https://mem0.ai/blog/mem0-the-token-efficient-memory-algorithm",
  "timeout_seconds": 3600
}
```

```json
{
  "hypothesis_id": "mem0-v3-llama8b-memoryarena",
  "claim": "Mem0 v3 with Llama 3.1 8B Q4 maintains >=60% on MemoryArena interdependent tasks (vs LoCoMo near-saturation), confirming agentic-memory utility not just recall",
  "metric": "memoryarena_avg_pct",
  "thresholds": {"confirm_at_least": 60.0, "refute_below": 40.0},
  "workload": "memoryarena-multisession.jsonl",
  "source_for_claim": "https://arxiv.org/abs/2602.16313",
  "timeout_seconds": 7200
}
```

```json
{
  "hypothesis_id": "letta-filesystem-llama8b-locomo",
  "claim": "Letta's 'filesystem + grep' agentic memory pattern with Llama 3.1 8B Q4 hits >=70% on LoCoMo (Letta claims 74% with GPT-4o-mini)",
  "metric": "locomo_accuracy_pct",
  "thresholds": {"confirm_at_least": 70.0, "refute_below": 55.0},
  "workload": "locomo-full.jsonl",
  "source_for_claim": "https://www.letta.com/blog/benchmarking-ai-agent-memory",
  "timeout_seconds": 3600,
  "decision_rule": "If small-model filesystem pattern lands within 10pp of Mem0 v3, this becomes the simpler default."
}
```

```json
{
  "hypothesis_id": "cognee-llama8b-graph-quality",
  "claim": "Cognee's graph extraction with Llama 3.1 8B Q4 produces graphs with <=20% hallucinated edges (Cognee docs claim >=90% hallucination at 8B; this tests our mesh-borrow workaround)",
  "metric": "hallucinated_edge_pct",
  "thresholds": {"confirm_at_most": 20.0, "refute_above": 50.0},
  "workload": "personal-conversation-corpus-1k-utterances.jsonl",
  "source_for_claim": "https://www.glukhov.org/ai-systems/memory/choosing-right-llm-for-cognee-on-ollama",
  "timeout_seconds": 1800
}
```

```json
{
  "hypothesis_id": "aider-repomap-1k-pagerank-fidelity",
  "claim": "Aider repomap PageRank + tree-sitter compressed view of a 100k-LoC corpus, at 1k token budget, retains >=80% of identifiers needed to answer a held-out set of 50 code-comprehension questions",
  "metric": "identifier_recall_pct",
  "thresholds": {"confirm_at_least": 80.0, "refute_below": 65.0},
  "workload": "selfhost-codebase-100kloc + comprehension-50q.jsonl",
  "source_for_claim": "https://aider.chat/docs/repomap.html",
  "timeout_seconds": 1200
}
```

```json
{
  "hypothesis_id": "continue-hybrid-vs-pure-vector",
  "claim": "Continue.dev's hybrid retrieval (LanceDB + ripgrep + LLM rerank) outperforms pure vector RAG by >=10pp on a code-question benchmark with Llama 3.1 8B Q4",
  "metric": "code_qa_accuracy_pct_delta",
  "thresholds": {"confirm_at_least": 10.0, "refute_below": 3.0},
  "workload": "code-questions-100q.jsonl",
  "source_for_claim": "https://lancedb.com/blog/the-future-of-ai-native-development-is-local-inside-continues-lancedb-powered-evolution/",
  "timeout_seconds": 1800
}
```

```json
{
  "hypothesis_id": "dspy-gepa-skill-portability",
  "claim": "A DSPy GEPA-compiled skill for 'extract entities from agent conversation' transferred via program.save/program.load reproduces accuracy within 2pp of in-process compilation",
  "metric": "skill_accuracy_pct_delta",
  "thresholds": {"confirm_at_most": 2.0, "refute_above": 5.0},
  "workload": "entity-extraction-200samples.jsonl",
  "source_for_claim": "https://dspy.ai/api/optimizers/GEPA/overview/",
  "timeout_seconds": 3600
}
```

### 6.5 Federated-memory recommendations

**Don't ship federated *memory* in v1, v2, or even v3.** The privacy primitives are not yet shippable; the research is research. Watch arxiv 2604.16548 (Mnemonic Sovereignty survey) and similar work on agent-memory privacy.

**Do ship federated *skills* starting v2.** DSPy GEPA's `save()`/`load()` plus the OCM mesh transport layer (libp2p/iroh) plus the bench framework's reputation primitives is enough to ship a "compiled skill marketplace" within the existing v2 scope. This is OCM's directly-architected network-effect lever, and it doesn't touch user data.

A v3 stretch: explore "federated memory ingest" where a user's local memory is encrypted with their own key and sent to a borrowed-stronger-model node for entity extraction, then returned and decrypted locally. The strong model never sees plaintext memory at rest. This is plausible with techniques from the secure-computation literature but is a research bet, not a product feature for v3 commit.

---

## Sources

[^letta-blog]: [Why Small LLMs Fail at Tool Calling](https://dev.to/anak_wannaphaschaiyong_11/why-small-llms-fail-at-tool-calling-the-shocking-discovery-from-our-llama-3b-benchmark-5lg)
[^why-small-llms-fail]: [Letta — Programmatic Tool Calling with any LLM](https://www.letta.com/blog/programmatic-tool-calling-with-any-llm)
[^cognee-ollama]: [Choosing the Right LLM for Cognee: Local Ollama Setup (Glukhov, 2025)](https://www.glukhov.org/ai-systems/memory/choosing-right-llm-for-cognee-on-ollama)
[^graphrag-bench-paper]: [When to use Graphs in RAG (arxiv 2506.05690, ICLR'26)](https://arxiv.org/html/2506.05690v3) and [GraphRAG-Bench repo](https://github.com/GraphRAG-Bench/GraphRAG-Benchmark)
[^mem0-token-efficient]: [Mem0 — Introducing The Token-Efficient Memory Algorithm](https://mem0.ai/blog/mem0-the-token-efficient-memory-algorithm)
[^openmemory-mcp]: [Mem0 — Introducing OpenMemory MCP](https://mem0.ai/blog/introducing-openmemory-mcp)
[^mem0-readme]: [Mem0 GitHub](https://github.com/mem0ai/mem0)
[^letta-filesystem]: [Letta — Benchmarking AI Agent Memory: Is a Filesystem All You Need?](https://www.letta.com/blog/benchmarking-ai-agent-memory)
[^zep-paper]: [Zep: A Temporal Knowledge Graph Architecture for Agent Memory (arxiv 2501.13956)](https://arxiv.org/abs/2501.13956)
[^memoryos]: [MemoryOS GitHub (EMNLP 2025 Oral)](https://github.com/BAI-LAB/MemoryOS)
[^amem]: [A-MEM: Agentic Memory for LLM Agents (arxiv 2502.12110, NeurIPS 2025)](https://arxiv.org/abs/2502.12110)
[^dsrag]: [dsRAG GitHub](https://github.com/D-Star-AI/dsRAG)
[^dspy-gepa]: [DSPy GEPA overview](https://dspy.ai/api/optimizers/GEPA/overview/) and [Reflective Prompt Evolution with GEPA](https://dspy.ai/tutorials/gepa_ai_program/)
[^hipporag-paper]: [HippoRAG 2 / "From RAG to Memory" (arxiv 2502.14802, ICML 2025)](https://arxiv.org/abs/2502.14802)
[^memoryarena]: [MemoryArena (arxiv 2602.16313, Stanford 2026)](https://arxiv.org/abs/2602.16313) and [MemoryArena project page](https://memoryarena.github.io/)
[^aider-repomap]: [Aider Repository Map](https://aider.chat/docs/repomap.html) and [Building a better repository map with tree sitter](https://aider.chat/2023/10/22/repomap.html)
[^repomix]: [Repomix GitHub](https://github.com/yamadashy/repomix)
[^continue-codebase]: [Continue.dev — @Codebase](https://docs.continue.dev/customize/context/codebase) and [LanceDB integration writeup](https://lancedb.com/blog/the-future-of-ai-native-development-is-local-inside-continues-lancedb-powered-evolution/)
[^roo-codebase]: [Roo Code — Codebase Indexing](https://docs.roocode.com/features/codebase-indexing)
[^augment-engine]: [Augment Context Engine](https://www.augmentcode.com/context-engine)
[^cline-no-index]: [Cline — Why Cline Doesn't Index Your Codebase](https://cline.bot/blog/why-cline-doesnt-index-your-codebase-and-why-thats-a-good-thing)
[^gitnexus]: [GitNexus writeup](https://www.aitoolskit.io/learn/gitnexus-code-knowledge-graph-ai-agents-2026)
[^code-context-paper]: [Compressing Code Context for LLM-based Issue Resolution (arxiv 2603.28119)](https://arxiv.org/abs/2603.28119)
[^flower]: [Flower federated learning framework](https://flower.ai/)
[^mit-ftte]: [MIT News — Privacy-Preserving AI Training on Everyday Devices (April 2026)](https://news.mit.edu/2026/enabling-privacy-preserving-ai-training-everyday-devices-0429); paper at arxiv 2510.03165
[^agentic-fl]: [Agentic Federated Learning (arxiv 2604.04895)](https://arxiv.org/html/2604.04895)
[^mnemonic-sovereignty]: [A Survey on the Security of Long-Term Memory in LLM Agents (arxiv 2604.16548)](https://arxiv.org/html/2604.16548v1)

**Cross-cutting / additional:**
- [Microsoft GraphRAG GitHub](https://github.com/microsoft/graphrag)
- [LightRAG GitHub](https://github.com/HKUDS/LightRAG)
- [Cognee GitHub](https://github.com/topoteretes/cognee)
- [Cognee state of memory comparison](https://atlan.com/know/best-ai-agent-memory-frameworks-2026/)
- [PathRAG (arxiv 2502.14902)](https://atalupadhyay.wordpress.com/2025/03/03/pathrag-the-evolution-of-graph-based-retrieval-augmented-generation/)
- [HippoRAG GitHub (OSU-NLP-Group)](https://github.com/OSU-NLP-Group/HippoRAG)
- [R2R GitHub](https://github.com/SciPhi-AI/R2R)
- [Verba GitHub](https://github.com/weaviate/Verba)
- [LlamaIndex HierarchicalNodeParser docs](https://developers.llamaindex.ai/python/framework-api-reference/node_parsers/hierarchical/)
- [LlamaIndex Auto Merging Retriever](https://developers.llamaindex.ai/python/examples/retrievers/auto_merging_retriever/)
- [MemoryScope / ReMe (Alibaba ModelScope)](https://github.com/modelscope/ReMe)
- [Sourcegraph Cody open-source snapshot](https://github.com/sourcegraph/cody-public-snapshot)
- [Mem0 — State of AI Agent Memory 2026](https://mem0.ai/blog/state-of-ai-agent-memory-2026)
- [MemoryAgentBench (arxiv 2507.05257)](https://arxiv.org/html/2507.05257v3)
- [Mem0 Open Source v2-to-v3 migration](https://docs.mem0.ai/migration/oss-v2-to-v3)
- [Memstate vs Mem0 vs Vector Search benchmark (April 2026)](https://memstate.ai/blog/ai-memory-benchmark-2026)
- [Cline vs Roo Code vs Continue (2026)](https://www.devtoolreviews.com/reviews/cline-vs-roo-code-vs-continue)
- [Inside Claude Code architecture](https://www.penligent.ai/hackinglabs/inside-claude-code-the-architecture-behind-tools-memory-hooks-and-mcp/)
- [Top 10 RAG Frameworks (Jan 2026)](https://florinelchis.medium.com/top-10-rag-frameworks-on-github-by-stars-january-2026-e6edff1e0d91)

---

## Confidence calibration

| Claim | Confidence |
|---|---|
| Mem0 v3 hits 91.6 LoCoMo / 93.4 LongMemEval | **Verified** (Mem0 own blog with reproducible code) |
| Mem0 is library-driven by default | **Verified** (README example) |
| Cognee requires 32B+ models | **Verified** (own docs + Glukhov writeup) |
| GraphRAG-Bench cross-cutting numbers | **Verified** (arxiv 2506.05690) |
| LightRAG: 70-90% of GraphRAG quality at 1/100th cost | **Vendor claim** (LightRAG marketing) |
| Letta filesystem 74% LoCoMo with GPT-4o-mini | **Verified** (Letta own blog, but they admit it's apples to oranges) |
| MemoryArena 40-60% drop from LoCoMo near-saturation | **Verified** (Stanford paper) |
| HippoRAG 2 +7% associative memory | **Verified** (paper) |
| Aider repomap mechanism | **Verified** (Aider docs) |
| Repomix --compress 70% token reduction | **Vendor claim** |
| Continue.dev architecture details | **Verified** (Continue + LanceDB blog) |
| Cline benchmarks vs indexed agents | **No data** — Cline publishes none; pattern is opinion |
| Augment "30-80% quality improvements" | **Vendor claim** (closed-source product) |
| MIT FTTE 81%/80%/69% efficiency | **Verified** (MIT News + arxiv 2510.03165) |
| "Federated memory works in production today" | **Refuted** — no shipping product; research only |
| DSPy GEPA save/load is portable | **Verified** (DSPy docs) |

When in doubt, treat vendor self-reported numbers as upper bounds and validate against the bench framework before locking decisions.
