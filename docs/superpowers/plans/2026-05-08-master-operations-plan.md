# OCM Master Operations Plan — Three Parallel Tracks

> **Status:** Plan only — no code yet. Execution begins after user confirms.
> **Date:** 2026-05-08
> **Strategic principle:** *"The fewer machines it takes, the more powerful it becomes as a large-scale mesh."* Every tool we adopt must be measured in isolation and in combination, with metrics that confirm efficacy. Meticulous and analytical — measure, don't assume.

This plan organizes work into three orthogonal tracks that can run in parallel. Each track has its own detailed plan file. This document is the index and sequencing.

## Three tracks

| Track | What | Detailed plan | Where work lives |
|---|---|---|---|
| **A: Website** | `ocm.shortcircuit.bot` — landing, docs, roadmap, models, /research, /benchmarks, /contribute. Astro+Tailwind+SQLite to match Short Circuit ecosystem. | [`2026-05-08-ocm-website-plan.md`](2026-05-08-ocm-website-plan.md) | `OCR-Forge/workspaces/OCM/` |
| **B: v1 Daemon Code** | Tauri shell, supervisor, OpenAI-compat API, MCP adapter, web UI, Mem0 integration, vLLM/llama.cpp adapters, installer | [`2026-05-08-ocm-v1-implementation-plan.md`](2026-05-08-ocm-v1-implementation-plan.md) | `opencircuitmodel/` |
| **C: Benchmark + Sandbox Framework** | Isolation sandboxes (per-tool), combination sandboxes (per-stack), blind A/B testing, retro-sync regression analysis, metrics dashboard. **Every locked decision in the spec gets a measurement that confirms or refutes it.** | [`2026-05-08-ocm-bench-framework-plan.md`](2026-05-08-ocm-bench-framework-plan.md) | `opencircuitmodel/bench/` |

## Why three tracks in parallel

- They have **zero shared state**. Website is Astro/TS, daemon is Rust/Python/Svelte, bench is Docker/Python.
- Each track delivers **independent value**. The bench framework is useful even if v1 daemon ships late (it validates every borrowed tool). The website is useful before v1 ships (sets expectations, recruits contributors). v1 code is the product.
- Bench and v1 inform each other: **every claim in the v1 spec gets a benchmark.** When research said "EAGLE-3 gives 1.5-2.5×" — we measure it ourselves before locking it on by default. When research said "Mem0 fits small models better than Letta" — we measure it ourselves.
- Website pulls live data from bench results — `/benchmarks` page is auto-generated from the bench framework's output.

## Sequencing — what happens when

### Phase 0 — Foundations (Weeks 1-2, parallel work)

| Track | Phase 0 deliverable |
|---|---|
| A (Website) | Astro scaffold, theme, nav, /, /docs, /roadmap, /research pages live locally. Deployed to Railway. |
| B (v1 Code) | Tauri shell + system tray + paths + settings + CI green on macOS/Win/Linux (Tasks 1.1-1.7 of implementation plan). |
| C (Bench) | Bench framework scaffold, first 3 isolation sandboxes (vLLM, llama.cpp, Mem0), CI integration, results dashboard. |

**Phase 0 gate:** All three tracks have something working locally. Website hits a real domain. Daemon launches a tray icon. Bench framework runs `bench run --isolation vllm-q4-llama8b` and produces a numbered result.

### Phase 1 — Core integration (Weeks 3-6)

| Track | Phase 1 deliverable |
|---|---|
| A (Website) | /models page wired to live registry, /benchmarks page wired to bench results, /contribute with hardware-recommendation calculator |
| B (v1 Code) | Mem0 + vLLM/llama.cpp + Tauri all wired together; first end-to-end "chat with your local agent" works (Tasks 1.8-3.5) |
| C (Bench) | First combination sandbox: full v1 stack measured. Compare against research-claimed numbers. Either confirm or revise spec. |

**Phase 1 gate:** A user installing a local-build OCM and chatting with an agent that remembers them = working. The benchmark framework has confirmed (or revised) the per-node multiplier claims from research.

### Phase 2 — API surface + UI (Weeks 7-10)

| Track | Phase 2 deliverable |
|---|---|
| A (Website) | /research and /benchmarks fully populated; /download with prebuilt installer links from CI artifacts |
| B (v1 Code) | OpenAI-compat HTTP + MCP server adapter + web UI (Tasks 4.1-5.6) |
| C (Bench) | Quality benchmarks (MMLU, GSM8K, tool-call correctness, memory recall) integrated. Per-tool blind A/B. |

### Phase 3 — Release prep (Weeks 11-12)

| Track | Phase 3 deliverable |
|---|---|
| A (Website) | Launch-day polish, Show HN draft, blog scaffolding |
| B (v1 Code) | Installers + first-run flow + smoke tests (Tasks 6.1-6.10) |
| C (Bench) | Full v1 release benchmark suite — published numbers, reproducible, third-party-runnable |

### Phase 4 — Public alpha (Week 13+)

- v1.0.0-alpha released
- Recruit 5 closed-alpha contributors (the math from this document)
- Website goes live publicly
- Bench framework public — anyone can verify our claims

## Contributor sizing — meticulous math

### The fundamental question

**How few contributor machines deliver compelling top-tier outcomes day one?**

### Per-node capacity (top-tier model: Qwen3-30B-A3B MoE)

| Hardware | Single-stream tok/s | Aggregate w/ batching | Concurrent users (peak factor 4×, 30% headroom) |
|---|---|---|---|
| RTX 4090 24GB | 120-196 | 400-650 | **50-100 users** |
| RTX 5090 32GB FP4 | 200-300 | 600-900 | **75-150 users** |
| M4 Pro 64GB MLX | ~130 (single-stream, batching limited) | 130-200 | **30-50 users** (batching cap) |
| M4 Pro 32GB | 60-90 (single-stream, 8B fallback) | 100-150 | **25-40 users** (8B Q4) |
| RTX 4060 8GB (8B fallback) | 40 | 100-150 | **25-40 users** (8B Q4) |

### Tiered fleet sizing

For a beta where the user experience is **always top-tier (30B-A3B MoE, sub-3s TTFT, 30+ tok/s sustained)** with **at least 1 redundant high-spec node** so a single contributor going offline doesn't break the experience:

**Tier 1 — Closed alpha (the "5 contributors" answer):**
- 3× high-spec (4090 / 5090 / M4 Pro 64GB) running Qwen3-30B-A3B MoE
- 2× mid-spec (M4 Pro 32GB / RTX 4060+) running Qwen3 8B Q4 as overflow + edge cases
- **Total: 5 contributor nodes**
- **Supports: 150-300 concurrent beta testers** at top-tier quality
- Hardware cost if self-funded: ~$10K-$15K (or volunteer-supplied)

**Tier 2 — Compelling beta (the "validate the thesis" tier):**
- 5× high-spec + 5× mid-spec = **10 contributor nodes**
- Supports **400-700 concurrent testers**
- This is where word-of-mouth begins — beta testers tell their friends
- Hardware cost: ~$25K-$35K self-funded; 10 enthusiast volunteers more realistic

**Tier 3 — Open beta (the "viable launch" tier from earlier research):**
- 15× high-spec + 15× mid-spec = **30 contributor nodes**
- Supports **1500-2500 concurrent users**
- Network effect kickoff territory — must scale infra to absorb growth

**Tier 4 — Self-sustaining (months 12-24):**
- 100+ contributor nodes
- 5K-10K active users
- Foundation/grant-funded operationally

### Recruitment math (where do the first 5 come from?)

Realistic candidate pool for contributor recruitment:

| Source | Likely contributors (first 5-10) | Why |
|---|---|---|
| **Brand's existing contacts** | 1-2 | OCR Racing community, Open Circuit Dev contributors, friends with capable hardware |
| **r/LocalLLaMA enthusiasts** | 1-2 | Self-selected for caring about local AI; many already run vLLM/Ollama |
| **Hacker News launch** | 1-2 | First-week organic interest if the launch demo is compelling |
| **Twitter/X niche AI builders** | 1 | Hardware-rich AI tweeters who'd run a node for the screenshot |
| **University AI/HPC labs** | 0-1 | If we explicitly invite — Astera/Berkeley/Cornell/Stanford have GPU surplus |

**Honest read: 5 contributors is achievable in 1-2 weeks of focused recruitment** if launch demo is compelling. 10 in 4-6 weeks. 30 in 3-6 months. 100+ in year 2.

### Beta tester sizing

- **Tier 1 beta:** Manual onboarding, ~50-100 testers (within capacity ceiling). Recruit via friends + online communities. Surveys + 1:1 feedback loops.
- **Tier 2 beta:** Open signup, ~250-500 testers. Self-service. Public Discord. Aggregated analytics.
- **Tier 3 launch:** Public, 5K-10K users target. Open documentation. Community-driven.

## Engineering discipline — the bench-framework principle

**Every single locked decision in the spec must have a benchmark.** Research is a hypothesis. Measurement is confirmation. We do not assume; we measure.

The bench framework (Track C) makes this concrete:

1. For every tool we adopt — vLLM, SGLang, llama.cpp, Mem0, EAGLE-3, Qwen3-30B-A3B, Hermes tool format, schema compression, etc. — there is an **isolation sandbox** that measures it alone against a baseline.
2. For every claimed multiplier — "RadixAttention gives 2.5×", "EAGLE-3 gives 1.5-2.5×", "schema compression saves 30-60% tokens" — there is a **measured number from our own runs** that confirms, refutes, or revises the claim.
3. For every combination — "vLLM + Q4 + RadixAttention + EAGLE-3 + 30B-A3B" — there is a **combination sandbox** that measures the full stack vs. the baseline and against the sum of individual multipliers.
4. Every measurement is **reproducible** (Docker-pinned, version-locked, deterministic seeds where possible) and **versioned** (every run output stored as Parquet with full provenance).
5. Every measurement is **anonymized for evaluation** — when human-eval'ing quality (e.g., "is this output better"), evaluators don't know which tool produced which output.
6. Every measurement is **retro-syncable** — running the same hypothesis on a v0.5 stack vs v0.7 stack reveals regressions immediately.
7. Every measurement is **publishable** — `/benchmarks` page on the website is auto-generated from these results. Anyone can re-run.

This is the engineering hygiene OCM needs to make sure we are achieving the outcomes we intend to achieve.

## Verification gates

| Gate | When | Pass criteria |
|---|---|---|
| **Phase 0 gate** | End of week 2 | All 3 tracks have something running locally; bench framework has produced its first measured result |
| **Phase 1 gate** | End of week 6 | Local OCM chats with persistent memory; bench framework has confirmed (or revised) the v1 stack's claimed per-node multiplier |
| **Phase 2 gate** | End of week 10 | OpenAI-compat + MCP both work with external clients (Claude Code, Cline, Continue.dev); quality benchmarks integrated |
| **Phase 3 gate** | End of week 12 | Cross-platform installers build; smoke test passes on macOS / Windows / Linux; full release benchmark published |
| **Phase 4 gate** | Week 13 | v1.0.0-alpha tagged; 5 closed-alpha contributors recruited; website public; first 50 testers onboarded |

## Risk callouts (operational)

| Risk | Likelihood | Mitigation |
|---|---|---|
| Bench framework reveals a research-claimed multiplier doesn't reproduce | Medium-High | The whole *point* of the framework is to catch this. Revise spec immediately, document. This is a feature, not a failure. |
| 5 closed-alpha contributors hard to recruit | Medium | Have demo video ready before recruitment; offer recognition (founding-contributor badge); seed with 1-2 friend contributors first |
| Website lags behind v1 (no public face on launch day) | Low | Phase 0 ships static landing; phases just add data |
| v1 daemon is more work than 12 weeks | Medium-High | Phase gates allow scope cuts; v6 (sharded inference) is already deferred; further deferrals possible at each gate |
| Bench framework grows into its own product (scope creep) | Medium | Bench is **internal-first**. Public publication is a side effect, not the goal. Resist any feature that doesn't directly serve OCM's measurement needs. |

## What this plan is NOT

- It is not a marketing plan. We pitch the project after it works, not before.
- It is not a fundraising plan. NLnet application happens around month 6 once we have 1K stars + 30 active nodes (per investment research).
- It is not a community plan. Discord + GitHub Discussions are setup chores, not strategic priorities.
- It is not a tokenization plan. There is no token. Reserve that decision for v3+ if needed.

## Index of all OCM planning documents

- [OCM v1 Design Spec v0.2](../specs/2026-05-08-ocm-v1-design-spec.md) — locked architectural decisions
- [OCM v1 Implementation Plan](2026-05-08-ocm-v1-implementation-plan.md) — task-by-task TDD plan for Track B
- **[OCM Bench Framework Plan](2026-05-08-ocm-bench-framework-plan.md)** — Track C detail
- **[OCM Website Plan](2026-05-08-ocm-website-plan.md)** — Track A detail
- **This document** — operational sequencing and contributor sizing
- [Tool Landscape Synthesis](../research/2026-05-08-tool-landscape-synthesis.md) — research foundations
