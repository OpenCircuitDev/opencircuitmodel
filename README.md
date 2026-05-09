# OpenCircuitModel (OCM)

> A free, open-source personal AI agent that lives on your machine, remembers everything, and grows in capability as the mesh grows. Apache 2.0 licensed.

**Status:** Pre-v1 — design and research phase. No installable artifact yet. Spec, implementation plan, and tool-landscape research are committed; v1 development begins after this initial commit.

**Website (planned):** [ocm.shortcircuit.bot](https://ocm.shortcircuit.bot) — under the [shortcircuit.bot](https://shortcircuit.bot) ecosystem.

---

## What OCM is

A peer-to-peer mesh that gives every participant access to AI agent compute by sharing the idle GPU/NPU cycles of their own machine. SETI@home-style volunteer compute, bidirectional, AI-agent-focused.

**The user pitch:** "Your personal AI agent — lives on your machine, persistent memory, OpenAI-compatible API, free, private. Give compute when you're idle, draw compute when you need it."

**The contributor pitch:** "Run OCM on your Mac Mini or gaming PC. Other users access AI through your idle GPU; you get cloud-tier agent capability through theirs."

OCM is built as a **stack of borrowed open-source frameworks plus a thin original orchestration layer** — vLLM/SGLang for inference, llama.cpp for Apple Silicon, Mem0 for persistent memory, libp2p/iroh for mesh transport, MCP + OpenAI-compat for the client API. The novel work is the orchestration and reciprocity ledger.

## What ships when

| Version | What | Effort | Status |
|---|---|---|---|
| **v1** | Single-node personal agent — works standalone, no mesh required | 8-12 wks | **In design** (this commit) |
| v2 | Two-node mesh via iroh / libp2p | 6-8 wks | After v1 |
| v3 | Reciprocity ledger (give-to-get accounting) | 4-6 wks | After v2 |
| v4 | Public bootnet + codesigned daemon | 4-6 wks | After v3 |
| v5 | Sandboxing + Sybil resistance | 6-10 wks | After v4 |
| v6 | Sharded inference for frontier models (Exo / Prima.cpp patterns) | 8-12 wks | After v5 |

v1 is a useful product on its own — a free, local, persistent AI agent with an OpenAI-compatible API and an MCP server. The mesh comes later.

## Why this might work

- Open foundation models (Llama 3.1, Qwen3, DeepSeek V3, Mistral) have closed the quality gap with closed cloud APIs
- The frameworks for distributed inference, efficient serving, mesh transport, and persistent agent memory all exist as mature OSS — OCM is mostly orchestration
- MCP and OpenAI-compatible APIs let any client (Claude Code, Cursor, Cline, Continue.dev, ChatGPT Connectors, Gemini, etc.) plug in immediately
- Consumer hardware — especially Apple Silicon Mac Mini class — is now genuinely capable of useful agent workloads
- Stacking efficiency multipliers (Q4 quantization × continuous batching × RadixAttention prefix-caching × EAGLE-3 speculative decoding × Qwen3-30B-A3B MoE) gets ~20-30× aggregate throughput per node, ~80× quality-adjusted, vs naive single-stream FP16 serving. Fewer machines deliver more aggregate compute than the naive math suggests.

## Why this might not work

OCM is a hard project, and we want to be honest about that.

- **Petals — the closest prior art for "BitTorrent-style LLM inference" — is functionally dead** as of 2026. Working tech, never crossed escape velocity.
- **Folding@home only mobilized millions during a galvanizing event** (COVID) and lost 99% of capacity post-event.
- **60% of solo OSS maintainers are unpaid; 60% are considering quitting; 44% cite burnout** (Tidelift 2024 survey).
- **Median GitHub Sponsors monthly income: $50.** Caleb Porzio's $100K/yr is exceptional.
- The **realistic best-case OSS exit** is the llama.cpp pattern — acquired by Hugging Face (Feb 2026) with team retained and full autonomy. Not IPO.

OCM-as-described is a 24-month bet on mission + learning + optionality. The realistic financial outcome distribution:

| Outcome | Probability |
|---|---|
| Burnout / archive at month 14 | 50-60% |
| Niche subsistence ($5-10K/mo blended income, real users) | 25-30% |
| Acquired/folded with team retained (llama.cpp pattern) | 10-15% |
| Foundation / open-core breakout ($200K-$2M ARR, small team) | 5-10% |

If you're considering contributing or running a node, do so because you believe in the mission. Not because you expect financial return.

## License

Apache 2.0 — see [LICENSE](LICENSE). Choose your own license for derivative works as Apache permits.

## Status of this repo

This is the initial commit. Everything in `docs/superpowers/` is the result of a brainstorming + research phase before code:

- [`specs/2026-05-08-ocm-v1-design-spec.md`](docs/superpowers/specs/2026-05-08-ocm-v1-design-spec.md) — the v1 design spec, with all locked architectural decisions and rationale
- [`plans/2026-05-08-ocm-v1-implementation-plan.md`](docs/superpowers/plans/2026-05-08-ocm-v1-implementation-plan.md) — task-by-task TDD-style implementation plan for v1
- [`research/2026-05-08-tool-landscape-synthesis.md`](docs/superpowers/research/2026-05-08-tool-landscape-synthesis.md) — synthesis of four research streams that informed the design
- `research/2026-05-08-per-node-efficiency.md` — inference engines, quantization, speculative decoding, MoE, Apple Silicon (~3,200 words, 60+ citations)
- `research/2026-05-08-mesh-distributed-compute.md` — Petals/Exo/Bittensor, libp2p/iroh, reciprocity precedents, network-effect data (~3,300 words)
- `research/2026-05-08-agent-memory-orchestration.md` — Letta vs Mem0, agent frameworks, DSPy, MCP ecosystem (~3,200 words)
- `research/2026-05-08-investment-market-viability.md` — comparable funding, grants, solo-OSS sustainability, honest outcome distribution (~3,200 words)

Code begins after this commit. Follow along on the planned subdomain at [ocm.shortcircuit.bot](https://ocm.shortcircuit.bot) (not yet live).

## Contributing

Contributions are welcome once code work begins. For now, the most useful contribution is critical reading of the spec and research — flag where the analysis is wrong, the assumptions are off, or the architecture has a hidden flaw. File issues at [github.com/OpenCircuitDev/opencircuitmodel/issues](https://github.com/OpenCircuitDev/opencircuitmodel/issues).

## Acknowledgments

OCM stands on the shoulders of every project named in the research synthesis: vLLM, SGLang, llama.cpp, MLX-LM, MLC-LLM, Mem0, Smolagents, DSPy, libp2p, iroh, Exo, Prima.cpp, Hivemind, Letta, Outlines, Instructor, Tauri, the MCP working group, and the Folding@home / BitTorrent / IPFS / Storj / Filecoin / Tor projects whose patterns inform the mesh and reciprocity design.
