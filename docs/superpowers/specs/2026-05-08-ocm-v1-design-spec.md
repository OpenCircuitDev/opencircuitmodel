# OpenCircuitModel (OCM) — Design Spec v0.2

> **Status:** brainstorming complete + research-driven revision (2026-05-08); implementation plan in `../plans/2026-05-08-ocm-v1-implementation-plan.md`
> **Date:** 2026-05-08 (revised same day after 4-stream subagent research — see `../research/2026-05-08-tool-landscape-synthesis.md`)
> **Project lead:** Brand (solo founder)
> **Repo:** `github.com/OpenCircuitDev/opencircuitmodel` (Apache 2.0)
> **Website:** ocm.shortcircuit.bot (subdomain under shortcircuit.bot ecosystem)

## Research-driven revisions in this version (v0.2)

Six load-bearing changes from the 2026-05-08 research synthesis:

1. **Memory layer: Letta → Mem0.** Letta's own engineering blog admits Llama 8B-Instruct cannot reliably drive its tool-calling memory paradigm — directly contradicts OCM's smaller-models-punch-above-weight thesis. Mem0's decoupled retrieval (library-driven, not LLM-driven) fits small models cleanly.
2. **Canonical model: Qwen3-30B-A3B MoE** (3.3B active / 30B total) for 24GB+ VRAM users. 120-196 tok/s on RTX 4090, quality competes with 70B dense. Smaller fallbacks (Qwen3 8B, Llama 3.1 8B, BitNet 2B) for lower-spec hardware.
3. **Sharded inference (v6): Petals → Exo / Prima.cpp.** Petals is functionally dead (`transformers==4.43.1` tombstone, last release Sept 2023, infra unreachable). Build on living code.
4. **Mesh transport (v2): libp2p → iroh primary with libp2p escape hatch.** Measured residential libp2p NAT success is 70%; iroh's QUIC-native traversal claims ~90%. The 20-percentage-point delta is the most important variable.
5. **Add to v1 inference defaults:** EAGLE-3 speculative decoding, Hermes XML+JSON tool format for small models (auto-detected), schema compression. All free, all measurable wins.
6. **Add Smolagents CodeAct as opt-in agent runtime.** 30% fewer steps, 30% fewer LLM calls, 50% less latency on representative workloads. JSON tool calling stays default; CodeAct is the power-user upgrade.

## Context

A free, open-source, peer-to-peer mesh that gives every participant access to cloud-level AI agent compute by sharing the idle GPU/NPU cycles of their own machine. Inspired by SETI@home's volunteer-compute model but bidirectional and AI-agent-focused. The user pitch: **"a personal AI agent that lives on your machine, remembers everything, and grows in capability as the mesh grows — give what you don't need, get what you can't afford."**

Why now:
- Open foundation models (Llama 3.1, DeepSeek V3, Qwen, Mistral) have closed the quality gap with closed cloud APIs
- Frameworks for distributed inference (Petals), efficient serving (vLLM), mesh transport (libp2p), and persistent agent memory (Letta) all exist as mature OSS — OCM is mostly orchestration
- MCP and OpenAI-compatible APIs let any client (Claude Code, Cline, Continue, Open WebUI) plug in immediately
- Consumer hardware — especially Apple Silicon Mac Mini class — is now genuinely capable of useful agent workloads

## Strategic framing

**Solo OSS with community** — open from day one, Apache 2.0, build in public, court grants from Mozilla / Sloan / Hugging Face / Anthropic OSS partners. No VC. Target the **"viable launch" tier** (1K contributors / 10K users) over 18-24 months, with **"viable beta"** (50 contributors / 500 users) as the 6-9-month proof-point.

## Locked decisions

| # | Decision | Choice | Rationale |
|---|---|---|---|
| 1 | Project name | **OpenCircuitModel (OCM)** | User-locked |
| 2 | Scope | AI-model-serving mesh (not generic compute) | "Model" in the name; tighter scope = better defensibility |
| 3 | Build approach | Stack of borrowed OSS frameworks + thin original orchestration | ~10-20K lines original code vs 100K+ rolled from scratch |
| 4 | License | **Apache 2.0** | Max adoption, foundation/grant-compatible, doesn't scare partners |
| 5 | Inference engine — NVIDIA peers | **vLLM v1 (default), SGLang v2 upgrade for prefix-heavy users** | vLLM = broadest ecosystem, lowest integration risk; SGLang RadixAttention = 2.5-5× on shared-prefix workloads (independent benchmarks) |
| 6 | Inference engine — Apple Silicon peers | **llama.cpp + Metal default; MLX-LM opt-in for advanced users** | llama.cpp most stable; MLX-LM 20-40% faster autoregressive but batching not yet vLLM-class production-mature |
| 6b | Inference engine — RTX 5090 / Blackwell | **TensorRT-LLM with FP4** | Only engine fully exploiting Blackwell FP4; ~2× over FP16 |
| 7 | Sharded inference (v6+) | **Exo (LAN ergonomics) + Prima.cpp (heterogeneous-cluster reference) + Hivemind DHT primitives** | Petals is functionally dead (transformers tombstone, no commits since Sept 2023); Exo is alive but LAN-only; Prima.cpp arxiv 2504.08791 is closest open prior art for OCM v6 |
| 8 | Mesh transport (v2+) | **iroh primary, libp2p as escape hatch via libp2p-iroh bridge** | libp2p residential NAT success 70% (measured 4.4M attempts); iroh ~90% (vendor-claimed, plausibly 80%+); iroh single-vendor risk mitigated by libp2p-iroh bridge keeping app protocols transport-agnostic |
| 9 | Agent memory + virtual context | **Mem0** (was Letta in v0.1) | Letta's own engineering admits Llama 8B can't reliably drive its tool-calling memory paradigm; Mem0's decoupled retrieval works with small models; v3 (April 2026) +20pp LoCoMo +26pp LongMemEval; 55k stars vs Letta's 22k |
| 10 | Agent runtime | **Lightweight ReAct loop default + Smolagents CodeAct opt-in** | LangGraph over-engineered for single-agent personal AI; CodeAct = 30% fewer steps, 30% fewer LLM calls, 50% lower latency on representative workloads |
| 11 | Client-facing API | **OpenAI-compat HTTP + MCP SDK** | Covers ~95% of existing clients (Claude Code, Cursor, Windsurf, Zed, Cline, Continue.dev, JetBrains, ChatGPT, Gemini, etc. — May 2026); MCP is now table-stakes |
| 12 | Daemon / cross-platform UI | **Tauri** (Rust + web) | Smaller binaries, better security, easier codesigning than Electron |
| 13 | Platforms | macOS + Windows + Linux from v1 | Tauri makes this cheap |
| 14 | Hero pitch | **"Free personal AI agent, always-on, persistent memory"** | (b) from killer-app menu |
| 15 | Wedge / secondary | Niche / fine-tuned models nobody else hosts (v3+) | (c) — peer-pool architecture supports this naturally |
| 16 | **Canonical model (24GB+ VRAM)** | **Qwen3-30B-A3B MoE** (3.3B active / 30B total) | 120-196 tok/s on RTX 4090, fits 24GB at Q4, quality competes with dense 70B; single biggest "small hardware, big quality" win |
| 17 | **Default model (8GB-16GB)** | Qwen3 8B Q4 / Llama 3.1 8B Q4 / Granite 4.0 (IBM, agent-tuned) | Stable workhorses; widely benchmarked |
| 18 | **CPU-only / tiny tier** | BitNet b1.58 2B (Microsoft, MIT) | Native ternary QAT, ~5-7× CPU throughput vs FP16 at 2B-8B |
| 19 | **Speculative decoding** | **EAGLE-3 default-on** (where engine supports) | Free 1.5-2.5× single-user speedup on consumer hardware; engines: vLLM, SGLang, TensorRT-LLM |
| 20 | **Tool-call format** | **Hermes XML+JSON for small models (auto-detected); OpenAI JSON for everything else** | Hermes-trained 8B models hit ~91% tool-call format accuracy vs Llama 3.1 native ~79%, Mistral 7B ~72% |
| 21 | **Schema compression** | **Default-on for MCP tool schemas** | 30-60% per-request token reduction with no model change; strip descriptions, shorten param names, hide optional params |
| 22 | **Structured generation** | **Instructor (user API) + engine-native (XGrammar / SGLang / llama.cpp grammar) + Outlines fallback for hard schemas** | 2-5× faster than Outlines as separate wrapper; Outlines kept for Kubernetes-grade complex schemas |
| 23 | **Optimization layer (v2+)** | **DSPy GEPA as opt-in `dspy.optimize_skill()` extension** | +10pp AIME, +17pp entity extraction; per-skill compile = power-user feature, compiled artifacts could redistribute via OCM mesh |

## v1 scope — "Single-Node OCM"

The simplest useful product: a personal AI agent that runs entirely on the user's machine with persistent memory, OpenAI-compat API, and MCP-server adapter. **Zero mesh dependencies in v1.** It must be useful even if no other OCM peer ever exists, because that's how you bootstrap trust before adding network complexity.

### A. User experience
1. Install OCM (one-line installer / .dmg / .exe / .deb)
2. Pick a model from a curated list (Llama 3.1 8B / Mistral 7B / Qwen 14B / Phi-3) — auto-downloads
3. Choose UI: web (`localhost:7300`), system tray quick-chat, or external client (Claude Code, Cline, etc. via OpenAI-compat / MCP)
4. Chat with your agent — it remembers across sessions via Letta paged memory
5. Quit anytime; resume tomorrow with full memory intact

### B. Architecture (v1)

```
┌──────────────────────────────────────────────────────────────┐
│  Clients:  OCM Web UI │ Claude Code │ Cline │ Continue.dev   │
└──────┬──────────────┬──────────────┬──────────────┬──────────┘
       │              │              │              │
       │ OpenAI-compat HTTP        MCP server      MCP server
       │              │              │              │
       └──────────────┴──────┬───────┴──────────────┘
                             ▼
       ┌─────────────────────────────────────────────────┐
       │  OCM Daemon  (Tauri — system tray + Rust core)  │
       │   • Process supervisor                          │
       │   • OpenAI-compat HTTP server                   │
       │   • MCP server adapter                          │
       │   • Settings UI                                 │
       └────────┬───────────────────────────────┬────────┘
                ▼                               ▼
       ┌─────────────────┐           ┌──────────────────────┐
       │  Mem0 +         │ ◀─────▶   │  Inference Backend   │
       │  ReAct Loop     │           │  • vLLM (NVIDIA)     │
       │  (Smolagents    │           │  • SGLang (v2)       │
       │   CodeAct       │           │  • TRT-LLM FP4 (5090)│
       │   opt-in)       │           │  • llama.cpp (Mac)   │
       └────────┬────────┘           │  • MLX-LM (M-series) │
                                     └──────────┬───────────┘
                ▼                               ▼
        ┌──────────────┐                ┌────────────────┐
        │  SQLite +    │                │  ~/OCM/models  │
        │  Vector DB   │                │  (cached       │
        │  (memory)    │                │   weights)     │
        └──────────────┘                └────────────────┘
```

### C. Components — what exists, what we build

| Component | Status | Lines of original code (est.) |
|---|---|---|
| OCM Daemon (Tauri shell, supervisor, settings) | **Build** | 3-5K |
| OpenAI-compat HTTP server (in daemon) | **Build** (thin shim over Letta) | 1-2K |
| MCP server adapter (bridges Letta → MCP) | **Build** | 1-2K |
| Web UI (chat, settings, model picker) | **Build** (React/Svelte) | 2-3K |
| Model registry (curated JSON, auto-download, verify) | **Build** | 0.5-1K |
| vLLM subprocess | Borrowed | Config only |
| llama.cpp subprocess | Borrowed | Config only |
| Letta agent runtime | Borrowed | Adapter only |
| Installer (macOS .dmg, Win .msi, Linux .deb/.rpm) | **Build** | Tauri toolchain |
| **Total v1 original code** |  | **~8-13K lines** |

### D. What's NOT in v1
- libp2p / mesh transport — v2
- Reciprocity ledger — v3
- Sharded inference (Petals) — v6
- Sandboxing for untrusted workloads — v5 (irrelevant in v1 — only own code runs)
- Multi-user-per-peer (single-tenant for now)
- Codesigned-for-public-trust installers — v4 (v1 ships as community-installable, advanced-user-friendly)

## Roadmap (v1 → v6)

| Version | Sub-project | Effort | Outcome |
|---|---|---|---|
| **v1** | Single-Node OCM (this spec) | 8-12 wks | Useful local agent. Standalone product. Foundation for mesh. |
| v2 | Two-Node Mesh (libp2p, naive routing) | 6-8 wks | Proves transport works end-to-end |
| v3 | Reciprocity Ledger v0 | 4-6 wks | Give-to-get accounting, simple ratio gate |
| v4 | Public Bootnet + Codesigned Daemon | 4-6 wks | Public alpha gate, AV-friendly |
| v5 | Sandboxing + Sybil Resistance | 6-10 wks | Open beta gate — adversarial-grade |
| v6 | Sharded Inference (Petals integration) | 8-12 wks | Frontier-model access (option-a unlock) |

**Calendar from start to viable beta tier:** ~36 weeks (~9 months) full-time solo. Achievable solo if scope is held; faster with 1-2 contributors joining post-v1.

## Scalability targets (Mac Mini reference)

| Tier | Contributors | Active users | Per-contributor capacity |
|---|---|---|---|
| Smoke test | 5-10 | 50-100 | ~25 users / M4 base Mini |
| Viable beta ⭐ | 50-100 | 500-1,000 | (target at month 9-12) |
| Viable launch ⭐⭐ | 500-1,000 | 5K-10K | (target at month 18-24) |
| Self-sustaining | 5,000+ | 50K-500K+ | (post-launch growth) |

## Verification plan — how do we know v1 works?

End-to-end manual smoke test (all on one machine):
1. **Install** — fresh-VM install on macOS / Windows / Linux completes without errors
2. **First-run** — daemon starts, picks reasonable defaults, downloads chosen model
3. **Chat** — open web UI at `localhost:7300`, send 10 messages, model responds in < 5 sec time-to-first-token on any reference machine
4. **Memory persistence** — quit OCM, restart, chat references prior conversation
5. **OpenAI-compat client** — point Cline / Continue.dev at `localhost:7300/v1`, see it work as a drop-in for OpenAI
6. **MCP client** — connect Claude Code via MCP, agent's memory and tools are accessible
7. **Long-context test** — 100K-token conversation that exceeds raw model context — Letta paging keeps it coherent
8. **Idle behavior** — daemon at idle uses < 50 MB RAM and 0% GPU; no leaks over 24 hours
9. **Uninstall** — clean uninstall removes daemon, models, memory at user's choice

Automated tests:
- Unit tests for the OpenAI-compat shim (request/response shapes)
- Unit tests for the MCP adapter (tool call routing)
- Integration test: scripted chat session that exercises memory recall across simulated restart
- Smoke test in CI for all three platforms

## Open implementation-phase questions (resolved in plan)

- Memory store: **SQLite + sqlite-vec** for v1 simplicity (Postgres optional via env var) — Mem0 supports both
- Model registry: **bundled JSON in v1** (Qwen3-30B-A3B + Qwen3 8B + Llama 3.1 8B + BitNet 2B), hosted manifest deferred to v2
- Auto-update: **Tauri's built-in updater** with public-key signing
- Telemetry: **none in v1** (defer until we have something worth measuring)
- Crash reporting: **local-only** (write to ~/.ocm/logs/, no remote in v1)
- Code structure: **Cargo workspace** with members `daemon`, `api`, `inference`, `mem0-adapter`, `models`, plus `frontend/` for the web UI

## Realistic outcome framing (per investment research)

OCM is a 24-month bet on **mission + learning + optionality**, not a path to founder income. The honest outcome distribution from comparable solo OSS distributed-AI projects:

| Outcome | Probability | What it looks like |
|---|---|---|
| Burnout / archive | 50-60% | Founder loses 18 months, learns a lot, returns to employment |
| Niche subsistence | 25-30% | Project lives, founder lives ($5-10K/mo blended), neither thrives |
| Acquired with team retained | 10-15% | The llama.cpp → Hugging Face outcome (Feb 2026) — best-case-realistic |
| Foundation / open-core breakout | 5-10% | Sustainable independent project, small team, $200K-$2M ARR |

**Required preconditions:**
1. ≥18 months runway *independent* of OCM income (savings, partner income, contract work paying 50% time)
2. A killer year-1 demo that hits HN front-page within 90 days
3. NLnet grant secured by month 6 (€20-50K, perfect thesis fit, multiple cycles per year)
4. Acceptance that P50 is "subsistence + mission" — not founder wealth
5. Year-3 exit plan with explicit checkpoint criteria (co-founder + open-core, foundation incubation, acquisition with team retained, or honorable archive)

This is documented honestly in the README. We don't pitch as a financial play.

## Repo and community kickoff (parallel track to v1)

- Public repo: `github.com/OpenCircuitDev/opencircuitmodel` (Apache 2.0)
- Project site: `opencircuitmodel.org` (or `.dev`)
- Community: Discord server + GitHub Discussions
- Launch posts: HN ("Show HN"), r/LocalLLaMA, r/selfhosted, Twitter/X
- Grant applications (queued for post-v1): Mozilla MIECO, Sloan Foundation, NLnet, Hugging Face Sponsorships
