# OpenCircuitModel (OCM)

> A free, open-source personal AI agent that lives on your machine, remembers everything, and grows in capability as the mesh grows. Apache 2.0 licensed.

**Status:** **v1 mostly built, not yet released.** The daemon (Tauri + Rust) compiles end-to-end with HTTP + MCP API surfaces, library-driven Mem0 retrieval, llama.cpp / vLLM inference adapters, a SvelteKit chat UI, settings panel, and curated model registry. The release workflow is wired but no v0.1.0 tag has been cut yet. See "What's built" below for the per-crate state.

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
| **v1** | Single-node personal agent — works standalone, no mesh required | 8-12 wks | **Mostly built; pre-release** |
| v2 | Two-node mesh via iroh / libp2p | 6-8 wks | Trait scaffold landed; impl pending |
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

## What's built

### Daemon + API (Rust workspace)

| Crate | Role | State |
|---|---|---|
| `ocm-daemon` | Tauri desktop shell — system tray, settings, app paths, supervises subprocesses, hosts the API server. Tauri commands for settings (get/save) and model downloads (list/download). | Built |
| `ocm-api` | OpenAI-compat HTTP server (`/v1/models`, `/v1/chat/completions` with SSE streaming, `/v1/registry/models`). Library-driven Mem0 retrieval before every chat turn. Localhost-only auth middleware. | Built |
| `ocm-inference` | `InferenceBackend` trait + llama.cpp + vLLM adapters + supervisor. Auto-selects backend by platform. | Built |
| `ocm-memory` | Mem0 client (search before generation, persist after). | Built |
| `ocm-mcp` | MCP stdio JSON-RPC bridge. Lets Claude Code / Cursor / Cline / Continue.dev connect via standard MCP. | Built |
| `ocm-models` | Curated registry (5 GGUFs across tiny / default / canonical tiers) + streaming SHA256-verified downloader. Refuses unverified hashes. | Built |
| `ocm-mesh` | Mesh transport trait + iroh / libp2p stubs. Real implementations land in v2. | Scaffolded |

### Frontend (`frontend/`, SvelteKit 2 + Svelte 5 + adapter-static)

| Route | What | State |
|---|---|---|
| `/` | Chat UI with SSE streaming, model picker, abort-to-stop | Built |
| `/models/` | Browse the curated registry, download with status feedback (Tauri-only) | Built |
| `/settings/` | Edit all 7 settings.toml fields, save via Tauri command | Built |

Built with Tailwind v4, TypeScript strict mode, svelte-check 0 errors / 0 warnings.

### Bench framework (`bench/`)

Hypothesis-based sandbox runner. First isolation sandbox (`vllm-q4-llama8b` on RTX 4090) wired with `expected.json`. Multipass-fleet mesh-discovery sandbox stub committed for v2 activation.

### Release pipeline

`.github/workflows/release.yml` builds `.dmg` (mac aarch64 + x86_64), `.msi` (windows), `.deb` + `.AppImage` (linux) on tag push. Drafts a GitHub Release with auto-generated notes. Codesigning + auto-update deferred to v4 per spec. See [`docs/release-process.md`](docs/release-process.md).

### Design + research artifacts

Everything in `docs/superpowers/` informed the architecture:

- [`specs/2026-05-08-ocm-v1-design-spec.md`](docs/superpowers/specs/2026-05-08-ocm-v1-design-spec.md) — v0.5, 31 locked decisions across architecture, models, optimizations, privacy, deployment policy
- [`plans/2026-05-08-ocm-v1-implementation-plan.md`](docs/superpowers/plans/2026-05-08-ocm-v1-implementation-plan.md) — task-by-task implementation plan
- [`research/`](docs/superpowers/research/) — eight research notes covering per-node efficiency, mesh, memory, market viability, Memory Palace pattern, effective-context triad, encryption + compression, and remote-node deployment

### What's NOT built yet

- Real iroh/libp2p mesh transport (v2)
- Reciprocity ledger (v3)
- Codesigning + auto-update (v4)
- Sandboxing + Sybil resistance (v5)
- Sharded inference (v6)
- The five model SHA256 hashes in `crates/ocm-models/registry.json` — the downloader refuses empty-hash entries, so downloads no-op until hashes are committed
- Live deployment on [ocm.shortcircuit.bot](https://ocm.shortcircuit.bot) — domain reserved, site not yet up

## Contributing

Code contributions are welcome. Per-area:

- **Daemon / API** — Rust 1.78+, `cargo test --workspace` runs the suite locally. CI verifies fmt + clippy + tests across ubuntu / macos / windows.
- **Frontend** — Node 20+, `cd frontend && npm install && npm run dev` for HMR. `npm run check` for svelte-check + tsc.
- **Spec / research** — critical reading is still a high-leverage contribution. Flag where the analysis is wrong, the assumptions are off, or the architecture has a hidden flaw.

File issues at [github.com/OpenCircuitDev/opencircuitmodel/issues](https://github.com/OpenCircuitDev/opencircuitmodel/issues).

## Acknowledgments

OCM stands on the shoulders of every project named in the research synthesis: vLLM, SGLang, llama.cpp, MLX-LM, MLC-LLM, Mem0, Smolagents, DSPy, libp2p, iroh, Exo, Prima.cpp, Hivemind, Letta, Outlines, Instructor, Tauri, the MCP working group, and the Folding@home / BitTorrent / IPFS / Storj / Filecoin / Tor projects whose patterns inform the mesh and reciprocity design.
