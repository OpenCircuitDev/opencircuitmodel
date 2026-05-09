# OCM Tool Watchlist — Recurring Scan Cadence

> **Purpose:** This document is the executable checklist for OCM's recurring tool-landscape scan. Categories are tagged with rescan cadence (monthly / quarterly / semi-annually / on-event). A future subagent dispatch reads this file, runs the rescan for due categories, and emits a fresh dated report.
> **Established:** 2026-05-09
> **Last full scan:** 2026-05-09 (memory deep-dive). Comprehensive 20-category scan pending — see this file's "Pending tasks" section.
> **Next scheduled rescan:** 2026-06-09 (monthly categories) — see schedule per category below.

## How this watchlist gets used

A subagent dispatched with the prompt **"Re-run OCM tool scan; check `tool-watchlist.md` for what's due"** should:

1. Read this file, identify categories whose `next_due` date is ≤ today
2. For each due category, run the scan steps in the "Re-scan procedure" subsection
3. Compare findings against the prior scan baseline (linked per category)
4. Write a delta report to `research/YYYY-MM-DD-watchlist-rescan-<categories>.md` highlighting:
   - New projects that appeared since last scan
   - Existing projects that significantly changed (release cadence, breaking changes, license shift, archived/deprecated)
   - Projects we should reconsider for OCM stack inclusion based on movement
5. Update this file: bump `last_scanned` and `next_due` for the categories that were scanned
6. Open a GitHub issue tagged `tool-scan-update` summarizing the highest-impact deltas

## Cadence taxonomy

| Cadence | Why |
|---|---|
| **Monthly** | Categories where projects move fast; breaking changes happen between scans; OCM is materially affected by new entrants. |
| **Quarterly** | Stable-but-active categories; breaking changes happen but predictably. |
| **Semi-annually** | Mature categories where the leaders are stable for months at a time. |
| **On-event** | Triggered by external events (new model release, paper publication, vendor acquisition). |

## Categories — the watchlist

### MONTHLY scans (high churn)

#### M1. Agent memory + sub-context retrieval
- **Last scanned:** 2026-05-09 ([deep-dive report](2026-05-09-memory-context-retrieval-deep-dive.md))
- **Next due:** 2026-06-09
- **Why monthly:** Mem0/Letta/Zep/Cognee shipping breaking changes monthly; new entrants (HippoRAG2, MemoryOS, A-MEM, dsRAG) appear regularly; benchmark methodology evolving (LoCoMo → MemoryArena)
- **Watch URLs:**
  - https://github.com/mem0ai/mem0 — releases page
  - https://github.com/letta-ai/letta — release notes for "library-driven mode"
  - https://github.com/getzep/graphiti — SQLite-backed alternative?
  - https://github.com/topoteretes/cognee — small-model improvements?
  - https://github.com/microsoft/graphrag — indexing cost reductions
  - https://github.com/HKUDS/LightRAG — production readiness
  - arXiv search: `("agent memory" OR "context retrieval") AND ("benchmark" OR "evaluation")` past 30 days
- **Triggers an immediate scan:** Letta or Mem0 announces a 1.x version bump

#### M1b. Decentralized memory palace / agent knowledge stores (added 2026-05-09)
- **Last scanned:** 2026-05-09 ([Memory Palace pattern analysis](2026-05-09-decentralized-memory-palace-pattern.md))
- **Next due:** 2026-06-09
- **Why monthly:** This is OCM's newly-locked third network-effect lever (v3.5+); the substrate space (git CRDT, iroh-blobs, p2p notes apps) is moving fast in 2026
- **Watch URLs:**
  - https://github.com/n0-computer/iroh-blobs — content-addressed blob store, OCM mesh transport partner
  - https://automerge.org/ — CRDT for collaborative markdown merge
  - https://github.com/orbitdb/orbitdb — IPFS-backed distributed database
  - https://earthstar-project.org/ — p2p personal-data store
  - https://github.com/anyproto/any-sync — Anytype's p2p sync protocol (mostly-OSS)
  - https://github.com/logseq/logseq — local-first knowledge graph
  - https://github.com/foambubble/foam — VS Code PKM
  - https://radicle.xyz — peer-to-peer code/git collaboration
  - Search arxiv: `("knowledge graph" OR "memory palace") AND ("agent" OR "LLM") AND ("p2p" OR "federated")` past 30 days
- **Triggers an immediate scan:** Anytype open-sources their full sync layer; any "agent memory federation" paper with shipping code; iroh-blobs adds git-replication primitives

#### M2. Agent frameworks (orchestration)
- **Last scanned:** 2026-05-08 ([orchestration report](2026-05-08-agent-memory-orchestration.md))
- **Next due:** 2026-06-08
- **Why monthly:** LangGraph, CrewAI, Smolagents, Pydantic AI, DSPy all shipping monthly; new entrants frequent
- **Watch URLs:**
  - https://github.com/langchain-ai/langgraph
  - https://github.com/crewAIInc/crewAI
  - https://github.com/huggingface/smolagents
  - https://github.com/pydantic/pydantic-ai
  - https://github.com/stanfordnlp/dspy — GEPA derivatives
  - https://github.com/ag2ai/ag2
  - **AutoGen ecosystem** — Microsoft's AutoGen successor
- **Triggers an immediate scan:** Microsoft ships a successor to AutoGen with breaking changes

#### M3. MCP ecosystem (servers, clients, SDKs)
- **Last scanned:** 2026-05-08
- **Next due:** 2026-06-08
- **Why monthly:** MCP exploded from 2024 launch; new servers added daily; client implementations expanding
- **Watch URLs:**
  - https://github.com/modelcontextprotocol/servers — official + community
  - https://github.com/modelcontextprotocol/python-sdk
  - https://github.com/modelcontextprotocol/typescript-sdk
  - **Rust MCP SDK** — track maturity (currently `rmcp` candidate)
  - Search GitHub topic `mcp-server` and trending
- **Triggers an immediate scan:** Anthropic publishes a major MCP spec revision

#### M4. Open frontier models for OCM canonical use
- **Last scanned:** 2026-05-08
- **Next due:** 2026-06-08
- **Why monthly:** Qwen, Llama, DeepSeek, Mistral, Granite, Phi all on monthly cadence; MoE landscape evolving fast
- **Watch URLs:**
  - https://huggingface.co/Qwen — Qwen3 family successors
  - https://huggingface.co/meta-llama — Llama 4 / Llama-Nemotron cycle
  - https://huggingface.co/deepseek-ai
  - https://huggingface.co/ibm-granite — Granite 4.0 successors
  - https://huggingface.co/mistralai
  - **Hugging Face Open LLM Leaderboard** — top performers per parameter band
  - **r/LocalLLaMA** — sentiment + benchmark crowdsourcing
- **Triggers an immediate scan:** New SOTA open model in 7-30B range published

### QUARTERLY scans (active but stable)

#### Q1. LLM inference engines
- **Last scanned:** 2026-05-08 ([efficiency report](2026-05-09-per-node-efficiency.md))
- **Next due:** 2026-08-08
- **Why quarterly:** vLLM/SGLang/llama.cpp/MLX-LM/TensorRT-LLM all stable in features but ship optimizations regularly
- **Watch URLs:**
  - https://github.com/vllm-project/vllm — release notes for new attention algorithms, quantization support
  - https://github.com/sgl-project/sglang — RadixAttention evolution
  - https://github.com/ggerganov/llama.cpp — backend optimizations
  - https://github.com/ml-explore/mlx — Apple Silicon batching improvements
  - https://github.com/InternLM/lmdeploy
  - https://github.com/NVIDIA/TensorRT-LLM
  - https://github.com/turboderp-org/exllamav3
  - https://github.com/microsoft/BitNet
- **Triggers an immediate scan:** New inference engine cracks 2× speedup over baseline on production workloads

#### Q2. Quantization toolkits
- **Last scanned:** 2026-05-08
- **Next due:** 2026-08-08
- **Why quarterly:** Slower-moving than inference engines; new methods (AQLM 2-bit, EXL3, HQQ, BitNet 1.58) take time to mature
- **Watch URLs:**
  - https://github.com/turboderp-org/exllamav3
  - https://github.com/AutoGPTQ/AutoGPTQ
  - https://github.com/casper-hansen/AutoAWQ
  - https://github.com/Vahe1994/AQLM
  - https://github.com/mobiusml/hqq
  - https://github.com/microsoft/BitNet
- **Triggers an immediate scan:** A 2-bit method achieves <1% perplexity hit on 70B-class models

#### Q3. Speculative decoding
- **Last scanned:** 2026-05-08
- **Next due:** 2026-08-08
- **Why quarterly:** EAGLE-3 is current frontier; successors (EAGLE-4? new draft architectures?) emerge slowly
- **Watch URLs:**
  - https://github.com/SafeAILab/EAGLE
  - vLLM/SGLang spec-decode pages for new method support
  - Apple's ReDrafter
- **Triggers an immediate scan:** Independent reproduction of >3× speedup on consumer hardware

#### Q4. Distributed inference (mesh-aligned)
- **Last scanned:** 2026-05-08 ([mesh report](2026-05-08-mesh-distributed-compute.md))
- **Next due:** 2026-08-08
- **Why quarterly:** Petals dead; Exo/Prima.cpp moving but not monthly
- **Watch URLs:**
  - https://github.com/exo-explore/exo — internet-mesh roadmap (issue #848)
  - arxiv 2504.08791 (Prima.cpp paper) and any followup
  - https://github.com/PrimeIntellect-ai — INTELLECT-3 successor
  - https://github.com/learning-at-home/hivemind — Petals-replacement
  - https://github.com/Mesh-LLM/mesh-llm
- **Triggers an immediate scan:** Anyone ships internet-scale heterogeneous-inference at >10 active worker count

#### Q5. P2P transports
- **Last scanned:** 2026-05-08
- **Next due:** 2026-08-08
- **Why quarterly:** libp2p stable; iroh approaching 1.0; veilid niche
- **Watch URLs:**
  - https://github.com/n0-computer/iroh — 1.0 release? independent NAT-success benchmark?
  - https://github.com/libp2p/rust-libp2p — DCUtR improvements
  - https://github.com/veilid/veilid

#### Q6. Code-aware sub-context retrieval (Continue/Aider/Cline)
- **Last scanned:** 2026-05-09 (covered in memory deep-dive)
- **Next due:** 2026-08-09
- **Why quarterly:** Active products; evaluation methodology evolving
- **Watch URLs:**
  - https://github.com/continuedev/continue
  - https://github.com/Aider-AI/aider
  - https://github.com/cline/cline
  - https://github.com/RooVetGit/Roo-Code
- **Triggers an immediate scan:** Cline publishes benchmarks backing the no-index philosophy

#### Q7. Federated learning / federated agent infrastructure
- **Last scanned:** 2026-05-09 (Section 4 of memory deep-dive)
- **Next due:** 2026-08-09
- **Why quarterly:** Research-heavy, slow productization
- **Watch URLs:**
  - https://flower.ai/ — major releases
  - arxiv search: `("federated" OR "P2P") AND ("agent" OR "LLM")` past 90 days
  - MIT FTTE production status

#### Q8. Vector databases
- **Last scanned:** TBD
- **Next due:** 2026-08-09
- **Why quarterly:** Mature category but new entrants (LanceDB recent) and feature improvements
- **Watch URLs:**
  - https://github.com/qdrant/qdrant
  - https://github.com/lancedb/lancedb
  - https://github.com/chroma-core/chroma
  - https://github.com/weaviate/weaviate
  - https://github.com/asg017/sqlite-vec
  - https://github.com/pgvector/pgvector

#### Q9. Embeddings (open + leaderboards)
- **Last scanned:** TBD
- **Next due:** 2026-08-09
- **Why quarterly:** MTEB rankings shift; new SOTA models appear; small-but-strong embeddings (BGE, Stella, Nomic, MixedBread) competitive
- **Watch URLs:**
  - https://github.com/embeddings-benchmark/mteb — leaderboard updates
  - https://huggingface.co/spaces/mteb/leaderboard
  - https://github.com/FlagOpen/FlagEmbedding — BGE family
  - https://github.com/nomic-ai/contrastors

#### Q10. Structured generation
- **Last scanned:** 2026-05-08
- **Next due:** 2026-08-08
- **Why quarterly:** Outlines/XGrammar/Instructor are stable; engine-native (vLLM/SGLang) integrations evolving
- **Watch URLs:**
  - https://github.com/dottxt-ai/outlines
  - https://github.com/instructor-ai/instructor
  - https://github.com/guidance-ai/guidance
  - https://github.com/mlc-ai/xgrammar

### SEMI-ANNUAL scans (mature, slow-moving)

#### S1. Sandboxing / container runtimes
- **Last scanned:** TBD
- **Next due:** 2026-11-09
- **Why semi-annual:** Docker/Podman/gVisor/Hyperlight all stable; new entrants (E2B, Modal sandbox) emerge over months
- **Watch URLs:**
  - https://github.com/microsoft/hyperlight
  - https://github.com/google/gvisor
  - https://github.com/e2b-dev/E2B
  - https://github.com/modal-labs

#### S2. Daemon / cross-platform UI frameworks
- **Last scanned:** 2026-05-08 (Tauri locked)
- **Next due:** 2026-11-08
- **Why semi-annual:** Tauri/Electron/Wails stable; major versions ~yearly
- **Watch URLs:**
  - https://github.com/tauri-apps/tauri — Tauri 3 roadmap
  - https://github.com/wailsapp/wails

#### S3. Auto-update mechanisms
- **Last scanned:** TBD
- **Next due:** 2026-11-09
- **Why semi-annual:** Sparkle/WinSparkle/Tauri updater are mature
- **Watch URLs:**
  - https://github.com/tauri-apps/plugins-workspace/tree/v2/plugins/updater
  - Sparkle/WinSparkle release notes

#### S4. Logging / observability
- **Last scanned:** TBD
- **Next due:** 2026-11-09
- **Why semi-annual:** OpenTelemetry / tracing-rs / Loki stable
- **Watch URLs:**
  - https://github.com/open-telemetry — major spec revisions
  - https://github.com/tokio-rs/tracing

#### S5. Benchmarking / evaluation harnesses
- **Last scanned:** 2026-05-08
- **Next due:** 2026-11-08
- **Why semi-annual:** lm-evaluation-harness, lighteval, BFCL stable; new benchmarks (LongMemEval, MemoryArena, GAIA) appear quarterly but adoption is slow
- **Watch URLs:**
  - https://github.com/EleutherAI/lm-evaluation-harness
  - https://github.com/huggingface/lighteval
  - **MemoryArena** — production-ready release date
  - **GraphRAG-Bench** — community adoption

### ON-EVENT scans (triggered by external news)

| Trigger | What to scan |
|---|---|
| New SOTA open model in 7-30B band released | M4 (canonical model) immediately, M2 (agent frameworks) within 7 days |
| Petals or competing mesh project announces revival/major release | Q4 (distributed inference) immediately |
| Anthropic publishes major MCP spec revision | M3 (MCP) immediately |
| Major OSS license shift (e.g., a project moves from MIT to BUSL) | All categories — license-audit pass |
| New paper claims >2× per-node efficiency win | Q1 (inference engines) + Q3 (speculative decoding) immediately |
| Hugging Face acquires or strategically invests in a memory-layer project | M1 (memory) immediately |
| Federated-memory research paper with shipping code | Q7 (federated) immediately + reconsider OCM v3 mesh memory plans |

## Pending tasks

### Comprehensive 20-category scan (originally Subagent A)
- **Status:** Plan written but execution blocked when plan mode propagated to subagents on 2026-05-08
- **Where the plan lives:** `C:\Users\brand\.claude\plans\cozy-munching-flask-agent-ac8dbe558d3f8f73f.md`
- **Categories covered (would be):** All 20 listed in the bench framework plan plus items M1-S5 above
- **Action:** Re-dispatch in a fresh session with the prompt updated to explicitly state "you are NOT in plan mode; auto mode is on; execute the scan and write directly to the OCM repo"

### MemoryArena workload acquisition
- The bench framework plan ([sandbox-additions](../plans/2026-05-09-bench-sandbox-additions-from-research.md)) requires `memoryarena-multisession.jsonl` workload. Stanford's MemoryArena release status needs confirmation. If workload isn't public, OCM will need to synthesize an equivalent — flag for tracking.

### Subagent dispatch automation
- The user requested this scan as a recurring activity. To make recurrence trivial:
  - Schedule via the user's `schedule` skill: a quarterly recurring task that auto-dispatches a research subagent reading this file
  - The subagent prompt template is captured in `bench/scripts/dispatch_recurring_scan.md` (TBD — to be created at next iteration)

## Procedure: how a subagent runs a re-scan

When a future subagent gets dispatched to "run the OCM tool scan," it should:

1. **Read this file** (`tool-watchlist.md`).
2. **Compute due-list:** for each category, if `next_due` ≤ today's date, include it.
3. **Per due category:**
   a. Visit each Watch URL
   b. Compare GitHub stars / last release / open issues against prior scan baseline
   c. Search arxiv / Hugging Face for new entrants
   d. Note any breaking changes, license shifts, archive/deprecate signals
4. **Synthesize:** produce a markdown delta report at `research/YYYY-MM-DD-watchlist-rescan-<scanned-categories>.md`
5. **Update this file:** bump `last_scanned` and `next_due` for scanned categories
6. **If significant deltas (rough threshold: any locked OCM stack item has a credible replacement, or a watch-list item moves to HIGH OCM-fit):**
   a. Open a GitHub issue tagged `tool-scan-update` summarizing the recommended OCM action
   b. Reference the delta report in the issue
7. **Leave remaining items untouched** — partial scans are fine; categories not yet due stay queued.

## Honesty principles

- **Verified > vendor-claimed.** Every claim in a delta report should label its source.
- **A "no change" verdict is valuable.** If nothing material happened, say so; don't manufacture findings.
- **Project archive/deprecation is a positive finding.** It removes ambiguity.
- **Star count is a weak signal.** Adoption velocity (commits, PR merges, release cadence) matters more.
- **Author bus factor matters.** A 50k-star solo-author project is fragile; a 10k-star team-of-five project is more reliable.
