# OpenCircuitModel (OCM) v1 — Agent Stack Research

**Date:** 2026-05-08. ~3,200 words.

This research evaluates the agent stack locked into the current OCM v1 spec (Letta / LangGraph / Outlines + Instructor / OpenAI-compat + MCP) against current alternatives, with a specific lens on **how well each performs on 7B-13B open models that consumer hardware can actually run**. The stakes: if your memory layer or framework requires GPT-4-class reasoning to function, your "personal AI agent" thesis collapses on consumer hardware.

---

## 1. Agent memory / virtual context — current state

### Letta (formerly MemGPT)
- **GitHub: 22.5k stars, v0.16.7 (March 31, 2026), 7,463 commits, Python 99.5%.** Active. Letta-AI Inc. corporate-backed.
- **Architecture:** OS-inspired tiered memory (core context / recall / archival), **LLM-driven retrieval** — the model itself decides when to call `archival_memory_search`, `core_memory_replace`, etc.
- **Breaking changes 2024-2026:** Significant. v1.0 SDK (early 2026) renamed everything from camelCase to snake_case, switched all list endpoints to cursor pagination, reorganized client init, requires Letta server v0.14+. Earlier 0.6.1 → 0.6.2 was unstable (filed crash issue). The roadmap also shows "Context Repositories" — a planned rebuild using programmatic context management and git-style versioning, which means another architectural shift coming.
- **The critical small-model problem (load-bearing for OCM):** Letta's own engineering blog acknowledges "Llama 8B-Instruct cannot reliably maintain a conversation alongside tool calling definitions" because Letta's paradigm requires the model to interleave conversation with `archival_memory_search` calls. Letta is fundamentally designed around models smart enough to drive their own memory tools.
- **Community sentiment:** Production-capable but not turnkey for 7B/8B. Mistral 7B works only with multiple-sample voting and JSON-prefill tricks.

### Mem0
- **GitHub: 55.2k stars (largest in space), Node SDK v3.0.2 (May 7, 2026), Python 55% / TypeScript 35%.** Most active.
- **April 2026 v3 algorithmic upgrade:** single-pass extraction, entity linking, multi-signal retrieval. **+20 points on LoCoMo, +26 on LongMemEval** vs prior algorithm. Migration guide required — breaking.
- **Architecture:** Cloud-first by default (memories on Mem0 servers, OpenAI embeddings) but supports local/self-host. **Decoupled from agent runtime** — Mem0 just stores/retrieves, doesn't dictate how the model uses tools.
- **Small-model fit:** Better than Letta because retrieval is library-driven, not LLM-driven. The agent gets retrieved chunks injected; it doesn't have to *decide* to retrieve. That removes the hard requirement on model agentic competence.

### Zep (+ Graphiti core)
- **Graphiti: 25.8k stars, v0.29.0 (April 27, 2026), Python 99.3%.** Open-source temporal graph engine.
- Zep is the cloud product; Graphiti is the OSS core you can self-host on Neo4j/FalkorDB/Kuzu/Neptune.
- **Benchmark crown:** **71.2% on LongMemEval (GPT-4o)**, also reported as 63.8% in a different harness — methodology variance is real here. **94.8% on DMR** (vs Letta/MemGPT's 93.4%). P95 retrieval latency 300ms.
- **Architecture:** Bi-temporal knowledge graph — every fact has a validity window plus an ingestion timestamp. Hybrid search = semantic + BM25 + graph traversal. Graphiti MCP Server v1.0 shipped November 2025.
- **Small-model fit:** Excellent in principle — facts are pre-extracted into a graph, the model just receives clean triples. But **Graphiti depends on a model strong enough to extract entities and relations during ingest.** That extraction step usually wants GPT-4-class. You can use a small model for query-time and a stronger one for ingest, which is a viable hybrid for OCM.

### Bottom line — Section 1
The benchmark numbers are dominated by Zep/Graphiti and Mem0 v3. **Letta's locked status in the OCM spec is the riskiest single decision in the stack** because Letta's own docs concede small-model unreliability — that directly contradicts OCM's thesis. Mem0 (decoupled retrieval) is the single best fit for "smaller models punching above their weight" because it doesn't require the agent to drive its own memory tooling. Graphiti is the dark horse if OCM contributors are willing to run a graph DB.

---

## 2. Agent framework landscape

| Framework | Stars | Last release | Status | Best for |
|---|---|---|---|---|
| LangGraph | 31.6k | langgraph-cli 0.4.25 (May 7, 2026) | Active, enterprise-tier | Production graphs, audit/rollback |
| CrewAI | 50.8k | active April 2026 | Active, claims 12M+ daily executions | Role-based prototyping |
| AutoGen | 57.8k | python-v0.7.5 (Sept 30, 2025) | **MAINTENANCE MODE** — Microsoft steers users to Microsoft Agent Framework | Legacy only |
| AG2 (community fork) | community | v0.11.2 (Feb 2026) | Active fork | AutoGen v0.2 continuity |
| Smolagents | 27.2k | v1.24.0 (Jan 16, 2026) | Active, HF-backed | Code-agent local-LLM workflows |
| OpenHands | 72.9k | 1.7.0 (May 1, 2026) | Active, AI-driven dev platform | Coding agents, not general |
| Pydantic AI | 16.9k | v1.93.0 (May 9, 2026) | Very active | Single-agent, type-safe |
| DSPy | 34.3k | v3.2.1 (May 5, 2026) | Stanford-led, very active | Prompt/weight optimization (different layer) |
| Marvin | smaller | active | Prefect-backed | Decorator-style "AI in functions" |

**Production task-completion benchmark (2026):** LangGraph 76% / Smolagents 73% / CrewAI 71% / AutoGen 68%. On *complex* tasks the spread widens: LangGraph 62% / AutoGen 58% / CrewAI 54% / Smolagents 49%.

**For OCM's specific use case** — single, long-running personal agent — most multi-agent frameworks are over-spec. The relevant question is: what runs the *agent loop* on top of Letta/Mem0?

- **Letta's built-in runtime** is single-agent ReAct-style. Sufficient for v1 if you stay with Letta.
- **Smolagents' CodeAct** is the most interesting alternative for small models. The code-act paradigm uses **30% fewer steps and 30% fewer LLM calls** than JSON tool calling on multiple benchmarks. That's a multiplier directly aligned with OCM's "more out of small models" thesis. Smolagents is HF-backed, not corporate-volatile.
- **LangGraph** is over-engineered for v1 personal-agent use. It earns its complexity at 5+ node workflows with rollback requirements. For a single chat-loop with memory + tools, it's overkill.
- **AutoGen is dead** for new code per Microsoft. AG2 is the lifeline if anyone has v0.2 code; new projects should not adopt it.

### Bottom line — Section 2
Don't add a multi-agent framework on top of Letta unless you have a multi-agent need. **The Smolagents code-act paradigm is the most-aligned alternative to Letta's built-in runtime** for the smaller-models thesis — code as the action space removes a whole class of JSON-tool-call failures that small models suffer from.

---

## 3. DSPy — does the magic actually work?

**Short answer: yes, on specific tasks, with caveats.**

The most substantial recent evidence is **GEPA** (Agrawal et al., 2025, arXiv:2507.19457, accepted ICLR 2026 Oral), DSPy's reflective prompt optimizer:
- Outperforms GRPO (RL baseline) by **6% average, up to 20%**, with **35× fewer rollouts**.
- Outperforms MIPROv2 by 10%+ (e.g., **+12% on AIME-2025**).
- Pushes **GPT-4.1-Mini from 46.6% → 56.6% on AIME 2025** (+10pp).
- Reaches **93% on MATH** vs **67% with basic DSPy ChainOfThought**.

For specific extraction tasks: **GEPA improved Gemini 2.5 Flash Lite from 80.7% → 97.8% on M&A entity extraction** with a single light optimization run. That's roughly a 17pp jump on a small model.

DSPy's own README claim — "**770M T5 and Llama2-13B-chat compiled with DSPy are competitive with GPT-3.5 and expert-written prompt chains**" — is now 2+ years old, but the pattern holds with newer optimizers.

### The tradeoffs
- **Compile-time cost:** GEPA's reflective approach is cheaper than RL but you still pay 100s-1000s of LLM calls per optimization. Each optimization is per-task — you can't generalize.
- **Training data requirements:** Need a metric and ~50-200 labeled examples per module. For OCM contributors building personal agents, this is real friction.
- **Per-skill scope:** DSPy optimizes a *specific program*. It won't make a 7B model magically smart at everything — you optimize per workflow.

### Bottom line — Section 3
**DSPy is a real force multiplier and worth adding to OCM's spec, but as an opt-in skill-builder layer, not a default.** The pattern "smaller model + DSPy-compiled program for specific high-value skills (memory summarization, tool selection, code review)" is exactly OCM's thesis materialized. Don't put it on the v1 critical path — too much friction for casual users — but provide a `dspy.optimize(skill)` extension API.

---

## 4. Structured generation — production-grade options

The 2026 reference benchmark is **JSONSchemaBench** (Geng et al., arXiv:2501.10868), 10K real-world JSON schemas across six frameworks.

### Headline results (Llama-3.1-8B-Instruct, llama.cpp backend)
| Dataset | Outlines (compliance) | XGrammar (compliance) | Notes |
|---|---|---|---|
| GlaiveAI | 0.96 | 0.93 | Easy schemas, both fine |
| GitHub Easy | 0.83 | 0.87 | XGrammar slight edge |
| Kubernetes | 0.57 | 0.07 | **Outlines wins on hard schemas** |

- **Guidance** (Microsoft): fewest total failures across schemas, minimizes under-constrained errors, fastest end-to-end (skips generation steps via "guidance acceleration").
- **Outlines:** highest compliance on complex schemas but expensive grammar compilation (regex-based).
- **XGrammar:** lower compilation cost; collapses on highly nested schemas like Kubernetes.
- **Instructor:** wraps everything, "safest default for projects starting today, works everywhere, no learning curve, covers the 80% case."
- **vLLM v1 / SGLang:** v1 dramatically faster than v0; SGLang overlaps mask generation with GPU inference, achieving **3-5× higher throughput on long-shared-prefix workloads** vs default vLLM. SGLang's structured decoding has near-zero overhead vs baseline; vLLM's drops significantly at batch ≥ 8.

### Bottom line — Section 4
The current OCM spec has **both Outlines and Instructor** locked, which is actually defensible: Instructor for the high-level Python ergonomics, Outlines for guaranteed compliance on hard schemas with local models. **However:** if OCM ever moves the inference engine to vLLM/SGLang, prefer the engine's *built-in* guided decoding (XGrammar in vLLM, SGLang's overlapped masking) — they're 2-5× faster than running Outlines as a separate layer. **My adjustment recommendation: keep Instructor as the user-facing API, swap Outlines for the engine-native option whenever the engine supports it (xgrammar/llguidance/sglang).** Add `Guidance` to the spec for the rare complex-schema case where compliance >> ergonomics.

---

## 5. MCP ecosystem maturity (May 2026)

**Verdict: table-stakes.** Anthropic launched MCP late 2024. Where it is now:

- **>500 public MCP servers** (community-tracked, early 2026). Coverage across DBs (Postgres/MySQL/SQLite), file storage (Drive/Box/Dropbox), web scraping, messaging (Slack/email), project management.
- **Client adoption:** Native in Claude Code, Claude Desktop, Cursor, Windsurf, Zed, JetBrains AI Assistant, Cline, Continue.dev, Replit, VS Code (via GitHub Copilot). ChatGPT added MCP via Apps SDK + Connectors (April 2025). Google Gemini API + Vertex AI Agent Builder added MCP support March 2026. OpenAI Agents SDK supports MCP. Vercel AI SDK supports MCP.
- **Industry survey:** 67% of CTOs (Q1 2026) name MCP as their default agent-integration standard within 12 months.
- **Continue.dev caveat:** Their team pivoted mid-2025 from IDE extension to "Continuous AI" CLI (CI-enforced code checks). The IDE extension still works and supports MCP, but receives less investment. If you target it specifically, plan for less polish.

### Bottom line — Section 5
**Locking MCP in the OCM spec is correct and uncontroversial.** OpenAI-compat HTTP + MCP is now the universal duo — that combination is the strongest possible bet for client-side ubiquity. The risk has flipped: not supporting MCP would be the spec-killer.

---

## 6. Agent benchmark performance — what's possible with open models?

The May 2026 leaderboards:

**SWE-bench Verified:** Claude Mythos Preview 93.9% / Claude Opus 4.7 (Adaptive) 87.6% / GPT-5.3 Codex 85%. Open-source: **Kimi K2 Thinking, GLM-5, Qwen3-Coder-Next** lead. **Qwen3-Coder-Next (80B MoE, 3B active params)** is the standout — gets coding-agent performance from a model that fits on consumer hardware via MoE sparsity.

**GAIA:** Claude Sonnet 4.5 leads at 74.6% (Princeton HAL). Anthropic sweeps top 6.

**WebArena:** Claude Mythos Preview 68.7% / GPT-5.4 Pro 65.8% / Claude Opus 4.6 64.5%.

**Open-model performance ceiling on agent tasks:** The honest answer is "still well below frontier closed models on complex multi-step tasks, but the gap is closing fast on specific benchmarks." Qwen3-Coder-Next is the most credible single model right now for OCM-style local agents — MoE means inference is small-model-priced even though parameter count is moderate. Granite 4.0 (IBM) targets agent/tool/JSON natively, smaller and lighter than Qwen3-Coder-Next.

### Bottom line — Section 6
**The model that actually matters for OCM v1 is probably Qwen3-Coder-Next (3B active / 80B total) for users with the VRAM, with Qwen3 8B / Llama 3.1 8B / Granite 4.0 as the small-hardware fallback.** I haven't found published GAIA/WebArena scores for these specific small open models in the 7-13B range — that's a real "I don't know" that OCM should benchmark itself before launch.

---

## 7. Tool-calling efficiency

### Format winner for small open models
**Hermes-style XML+JSON wins on small models, and it's not close:**
- Hermes 3 (8B) maintains correct `<tool_call>` format **~91%** of the time across 3+-turn chains.
- Llama 3.1 8B native: **~79%**.
- Mistral 7B: **~72%**.
- Hermes 3 8B produces valid parseable JSON tool calls **~91%** of attempts vs **~85%** for Llama 3.1 8B vs **~78%** for Mistral 7B.

The Hermes training format (`<tools>...</tools>` for definitions, `<tool_call>...</tool_call>` for calls, JSON inside tags) buys ~12-19pp over Llama 3 native on small models.

### Token overhead is real
- A 20-tool MCP server adds **2-4k tokens per request** (most never used).
- A 40-tool GitHub MCP server adds **10-15KB schema per turn**. If the agent uses two tools, the other 38 are pure overhead.
- **Schema compression alone reduces per-request overhead by 30-60%.**

### CodeAct vs JSON tool calling
Microsoft Agent Framework's CodeAct support: **end-to-end latency cut ~50%, token usage cut >60%** in representative workloads by collapsing multi-step plans into a single executable code block. Smolagents reports the same pattern: 30% fewer steps and 30% fewer LLM calls vs JSON.

**Tiny-model standout: Qwen3:1.7B scores 0.960 Agent Score; lfm2.5:1.2B scores 0.920 at 1567ms latency** — almost 7× faster than Qwen3:1.7B with only 0.040 score loss. There's surprising agentic capacity at the sub-2B scale, but this is workload-specific.

### Bottom line — Section 7
**Three concrete recommendations:**
1. Adopt the **Hermes XML+JSON tool format** as OCM's default for small-model users (a +10-19pp tool-call accuracy bump for free).
2. **Schema compression** must be a first-class feature — strip descriptions, shorten parameter names, hide optional params in the default schema. Easy 30-60% win.
3. Offer **CodeAct as an alternative action mode** (Smolagents-style), particularly for users on smaller hardware. The 30-60% latency/token reduction is a force multiplier the small-model thesis demands.

---

## 8. Creative / non-obvious wins

Speculative; flagged where so.

### High-confidence
- **Speculative decoding.** Built into vLLM, SGLang, TensorRT-LLM as standard in 2025-2026. Real **8.8-58% speedups** on Qwen / Llama / DeepSeek-R1 / GPT-4o; zero accuracy cost. Should be on by default in OCM's recommended inference config.
- **Test-Time Reinforcement Learning** boosts Qwen-2.5-Math-7B pass@1 by **~159% on AIME 2024** with only unlabeled test data. Compute-expensive but spectacular for specific reasoning skills.
- **Self-consistency / multi-sample voting.** Still the strongest verifier-free inference-time technique. Latent-Trajectory Early Accept reduces tokens **48-70% vs vanilla self-consistency** while improving accuracy 2.6%.

### Medium-confidence
- **Hybrid memory.** Use a stronger model (cloud GPT-4-class or local 30B+) for *ingest* (entity extraction into Graphiti), small local model for *query*. This sidesteps the Letta-style "small model can't drive its own tools" problem without abandoning the smaller-model thesis at runtime.
- **TOON (Token-Optimized Object Notation).** Compact JSON alternative for agent context. Niche but emerging in 2026 — could shave 10-30% off context size if it works as advertised. *Speculative.*
- **Skill compilation.** Per-skill DSPy GEPA compiles, distributed via OCM's mesh. If one contributor compiles a "summarize this conversation" skill that pushes Llama 8B from 70% → 90% accuracy on that specific task, every OCM user benefits. This is OCM's potential network effect — the agent layer literally getting smarter as the mesh grows.

### Speculative
- **Code-as-action becomes default action space.** Bet: by 2027, JSON tool calling looks dated. Smolagents, Microsoft Agent Framework CodeAct, and "the Python interpreter is the universal tool" pattern are converging.
- **Memory + retrieval becomes the new RLHF.** The "personal AI agent" v2 will be defined by what your agent *remembers about you*, not by which base model. OCM's mesh has a structural advantage here if memory is portable.

---

# Recommended agent stack for OCM v1

Rank-ordered, with reasoning:

### 1. Memory layer: **Mem0 over Letta** — switch the spec.
Letta's own engineering acknowledges Llama 8B-Instruct can't reliably drive its tool-calling memory paradigm. That's a direct thesis-violation for OCM. Mem0:
- Largest community (55k stars, active v3 release with concrete benchmark wins).
- **Decoupled architecture** — retrieval is library-driven, not LLM-driven. Small models don't have to *decide* to retrieve; they just receive retrieved chunks.
- Local self-host supported.
- LongMemEval +26pp gain in v3 vs prior (closes the gap to Zep/Graphiti).
- Cleaner integration with smaller models. **This is the single highest-ROI change to the OCM v1 spec.**

If Letta is sticky for political/contributor reasons, the fallback is a Letta+Mem0 hybrid where Letta runs the agent loop and Mem0 owns persistent memory (use Letta's `archival` as a thin proxy to Mem0). But the cleaner architecture is Mem0 alone.

**Future-watch:** Graphiti for v2. The bi-temporal graph is the most architecturally principled long-term-memory system in the field, but it requires Neo4j/FalkorDB/Kuzu/Neptune — too much install friction for "free personal AI agent" v1. Revisit when there's a SQLite-backed Graphiti or contributors regularly run a graph DB.

### 2. Agent runtime: **Letta's built-in runtime → Smolagents CodeAct option for small-model users**, not LangGraph.
LangGraph is over-engineered for a single-agent personal AI. If you swap Letta for Mem0, you need a runtime — Smolagents is the right pick:
- 27k stars, Jan 2026 release, HF-backed (institutional stability).
- **CodeAct paradigm** = 30% fewer steps and LLM calls than JSON tool calling. That's the smaller-models thesis directly materialized.
- ~1000 lines of agent logic — auditable, hackable, contributor-friendly.
- Strong local-model story (Ollama, Transformers, vLLM, llama.cpp).

Provide both modes: traditional JSON tool calling (default, works everywhere) and CodeAct (opt-in, faster, smarter on small models, requires sandbox).

### 3. Structured generation: **keep Instructor, drop Outlines as the default, add engine-native options.**
- **Instructor** (12.9k stars, multi-language, "safest default for new projects") = user-facing API, the 80% case.
- **Engine-native guided decoding** (XGrammar in vLLM, SGLang's overlapped masking, llama.cpp's grammar) = the actual constraint enforcer. 2-5× faster than Outlines as a wrapper.
- **Outlines** (13.8k stars) = optional dependency for the rare hard-schema case (Kubernetes-style) where compliance >> performance.
- **Guidance** (Microsoft) = optional dependency where complex branching JSON schemas are needed.

Phrase the spec as "schema-via-Instructor, decoding-via-engine, with Outlines/Guidance as escape hatches" rather than naming a specific schema-enforcement library.

### 4. Optimization layer: **DSPy as opt-in, not a critical path.**
DSPy 3.2 (May 2026) + GEPA (ICLR 2026 Oral) is the strongest force multiplier in the spec for small-model performance — **+10pp on AIME, +17pp on entity extraction, sometimes 90%+ on MATH from a 67% baseline.** But the per-skill compilation friction (need labels, need a metric, need rollouts) makes it wrong as a default. Best framing: **OCM v1 ships with a `dspy.optimize_skill()` extension API**. Power users compile skills (memory summarization, tool selection, code review). The compiled skill artifacts can be redistributed across the OCM mesh — every contributor's optimization benefits all users. **This is OCM's potential network effect**, and it's specifically the "smaller models punch above their weight" thesis turned into a system property.

### 5. Tool-calling format: **Hermes XML+JSON for small-model users; keep OpenAI-compat for everything else.**
The +12-19pp accuracy bump on small models from Hermes-style training is real and trivially adoptable. Auto-detect the model family at config time and pick the format.

### 6. Action format: **CodeAct as a first-class option, JSON tool calling as default.**
Smolagents-style code execution in a sandbox: 30% fewer LLM calls, 30% fewer steps, **50% lower latency, 60% lower token use** on representative workloads (Microsoft Agent Framework data). Sandbox requirement (E2B/Modal/Docker/WebAssembly) is real friction, so default to JSON; offer CodeAct as the power-user upgrade.

### 7. Inference defaults: **speculative decoding on, schema compression on, MCP locked.**
- Speculative decoding: 8-58% latency cut, free, in vLLM/SGLang/TensorRT-LLM.
- Schema compression: 30-60% token reduction with no model change.
- MCP: now table-stakes — keeping it locked is correct and not controversial.

### Summary of changes to OCM's locked spec
1. **Letta → Mem0** (single biggest fix).
2. **Add Smolagents** as runtime, with CodeAct opt-in.
3. **Instructor stays; Outlines becomes optional**, with engine-native guided decoding preferred.
4. **Add DSPy** as a skill-optimization extension (opt-in, not default).
5. **Add Hermes-format auto-detection** for small models.
6. **Lock speculative decoding + schema compression** as default inference behaviors.

The thesis you're betting on — "make the agent layer smart enough that smaller models punch above their weight" — is real and live in the literature (DSPy/GEPA, CodeAct, schema compression, speculative decoding, Hermes formats all deliver measurable wins specifically in the 7-13B range). The current OCM spec gets the API surface (OpenAI-compat + MCP) right but locks in **Letta**, which the framework's own engineers admit struggles with the model class OCM most needs to serve. Mem0 + Smolagents-CodeAct is the directly thesis-aligned alternative.

---

## Sources

**Section 1 — Memory:**
- [Letta GitHub](https://github.com/letta-ai/letta)
- [Mem0 GitHub](https://github.com/mem0ai/mem0)
- [Graphiti GitHub](https://github.com/getzep/graphiti)
- [Zep: A Temporal Knowledge Graph Architecture for Agent Memory (arXiv 2501.13956)](https://arxiv.org/abs/2501.13956)
- [Letta v1 SDK migration guide](https://docs.letta.com/api-overview/v1-migration-guide)
- [Letta — Programmatic Tool Calling with any LLM](https://www.letta.com/blog/programmatic-tool-calling-with-any-llm)
- [Why Small LLMs Fail at Tool Calling](https://dev.to/anak_wannaphaschaiyong_11/why-small-llms-fail-at-tool-calling-the-shocking-discovery-from-our-llama-3b-benchmark-5lg)
- [5 AI Agent Memory Systems Compared (2026)](https://dev.to/varun_pratapbhardwaj_b13/5-ai-agent-memory-systems-compared-mem0-zep-letta-supermemory-superlocalmemory-2026-benchmark-59p3)

**Section 2 — Agent frameworks:**
- [LangGraph GitHub](https://github.com/langchain-ai/langgraph)
- [CrewAI GitHub](https://github.com/crewAIInc/crewAI)
- [AutoGen GitHub (maintenance mode)](https://github.com/microsoft/autogen)
- [AG2 GitHub](https://github.com/ag2ai/ag2)
- [Smolagents GitHub](https://github.com/huggingface/smolagents)
- [OpenHands GitHub](https://github.com/All-Hands-AI/OpenHands)
- [Pydantic AI GitHub](https://github.com/pydantic/pydantic-ai)

**Section 3 — DSPy:**
- [DSPy GitHub](https://github.com/stanfordnlp/dspy)
- [GEPA: Reflective Prompt Evolution Can Outperform RL (arXiv 2507.19457, ICLR 2026 Oral)](https://arxiv.org/abs/2507.19457)

**Section 4 — Structured generation:**
- [JSONSchemaBench (arXiv 2501.10868)](https://arxiv.org/abs/2501.10868)
- [Outlines GitHub](https://github.com/dottxt-ai/outlines)
- [Instructor GitHub](https://github.com/instructor-ai/instructor)
- [Guided Decoding Performance — vLLM vs SGLang](https://blog.squeezebits.com/guided-decoding-performance-vllm-sglang)

**Section 5 — MCP:**
- [MCP Adoption Statistics 2026](https://www.digitalapplied.com/blog/mcp-adoption-statistics-2026-model-context-protocol)
- [9 Best MCP Clients 2026](https://fast.io/resources/best-mcp-clients-developers/)
- [MCP Servers GitHub](https://github.com/modelcontextprotocol/servers)

**Section 6 — Open-model agent benchmarks:**
- [SWE-bench Leaderboard](https://www.swebench.com/)
- [Berkeley Function Calling Leaderboard V4](https://gorilla.cs.berkeley.edu/leaderboard.html)
- [BenchLM SWE-bench Verified 2026](https://benchlm.ai/benchmarks/sweVerified)

**Section 7 — Tool calling:**
- [Hermes-3-Llama-3.1-8B (HuggingFace)](https://huggingface.co/NousResearch/Hermes-3-Llama-3.1-8B)
- [Anthropic — Code execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp)
- [Microsoft Agent Framework CodeAct](https://devblogs.microsoft.com/agent-framework/codeact-with-hyperlight/)
- [Reduce Token Usage in AI Agents](https://www.mindstudio.ai/blog/reduce-token-usage-ai-agents-mcp-optimization)

**Section 8 — Creative wins:**
- [Speculative Decoding 2026 (Premai)](https://blog.premai.io/speculative-decoding-2-3x-faster-llm-inference-2026/)
- [HF Blog — AI Trends 2026: Test-Time Reasoning](https://huggingface.co/blog/aufklarer/ai-trends-2026-test-time-reasoning-reflective-agen)
