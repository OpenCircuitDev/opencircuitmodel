# OpenCircuitModel (OCM) — Design Spec v0.6

> **Status:** v1 implementation mostly built (Phases 1-8 on main as of 2026-05-09); five research-driven revisions; implementation plan in `../plans/2026-05-08-ocm-v1-implementation-plan.md`
> **Date:** 2026-05-08 (v0.2) → 2026-05-09 (v0.3) memory deep dive → 2026-05-09 (v0.4) Memory Palace → 2026-05-09 (v0.5) VM/cloud policy → 2026-05-09 (v0.6) post-build hygiene + bench INACTIVE convention
> **Project lead:** Brand (solo founder)
> **Repo:** `github.com/OpenCircuitDev/opencircuitmodel` (Apache 2.0)
> **Website:** ocm.shortcircuit.bot (subdomain under shortcircuit.bot ecosystem)

## Build status (2026-05-09)

| Phase | What | Status |
|---|---|---|
| Phase 1 | Tauri shell, paths, settings, CI | ✅ on main (PR #1) |
| Phase 0 | Bench framework + first sandbox | ✅ on main (PR #2) |
| Phase 2 | Inference backends (llama.cpp + vLLM + supervisor) | ✅ on main (PR #17 megamerge) |
| Phase 3 | Mem0 client + library-driven retrieval | ✅ on main (PR #17) |
| Phase 4 | OpenAI-compat HTTP /v1/* + SSE streaming | ✅ on main (PR #17) |
| Phase 4.7 | Bootstrap module wiring | ✅ on main (PR #17) |
| Phase 4.6 | MCP stdio JSON-RPC bridge | ✅ on main (PR #17) |
| Phase 5a | SvelteKit chat UI + model picker | ✅ on main (PR #17) |
| Phase 5b | Localhost auth middleware | ✅ on main (PR #17) |
| Phase 5c | Settings panel + Tauri commands | ✅ on main (PR #17) |
| Phase 6 | Model registry + downloader + /models route | ✅ on main (PR #17) |
| Phase 7 | Cross-platform installers + release workflow | ✅ on main (PR #17) |
| Phase 8 | ocm-mesh crate scaffold (v2 prep) | ✅ on main (PR #17) |
| v2 | Real iroh / libp2p mesh transport | ⚠️ trait scaffold only |
| v3 | Reciprocity ledger | ❌ not started |
| v4 | Codesigning + auto-update | ❌ not started |
| v5 | Sandboxing + Sybil resistance | ❌ not started |
| v6 | Sharded inference | ❌ not started |

**Pre-release blockers before v0.1.0 tag:**
1. Populate `crates/ocm-models/registry.json` SHA256 hashes against canonical HF mirrors (downloader refuses empty-hash entries today; see `scripts/populate-registry-hashes.sh`)
2. Smoke test the daemon end-to-end on each platform (macOS aarch64 + x86_64, Windows, Linux)
3. Decision: ship without codesigning (v1) or wait for Apple Dev cert + Windows Authenticode (v4 per spec row 12)

## v0.6 revisions (2026-05-09)

One change (row 32):

1. **Bench-sandbox INACTIVE convention locked** (decision row 32 below). Sandboxes that test future-tech hypotheses (mesh transport, model registry hashes, real iroh impl) ship as slot-stubs containing only `expected.json` + `README.md`. The bench runner (`bench/bench/runner.py`) recognizes `status: "INACTIVE"` in `expected.json` and skips the docker-compose.yml + bench.py file requirement. ACTIVE sandboxes keep strict 4-file validation. The slot-stub pattern lets the harness commit early bets — the contract is fixed, the implementation lands when the underlying tech matures. Validates against the criticism that "bench-driven design" is over-engineered for a solo project: the slot-stub commits cost ~30 minutes each and pre-load the verification surface for whoever picks up Phase 7+ (mesh) or Phase 9+ (Memory Palace) work.

## v0.5 revisions (2026-05-09)

One change (row 31):

1. **VM / cloud deployment policy locked** (decision row 31 below). OCM v1 daemon runs on user-owned hardware by default. Remote VMs are supported in two specific shapes — bench/test fleets (any time, including the new `bench/isolation/mesh-transport/multipass-fleet/` sandbox stub) and Phase 7+ relay nodes (community-run, no user memory) — and explicitly NOT supported as a sanctioned "OCM on a VPS for inference" path in v1. Locks the implication that "local-first" means "this user's compute" not "this user's physical machine"; calls out the threat-model shift on a remote VM (Zone A encryption stops being defense-in-depth, becomes load-bearing; OS keyring substitution required); flags that Sybil resistance (v5+) is a hard precondition for encouraging remote-VM peers in inference sharing or palace federation. Full reasoning in [`../research/2026-05-09-remote-node-deployment.md`](../research/2026-05-09-remote-node-deployment.md).

## v0.4 revisions (2026-05-09)

Five changes (rows 26-30):

1. **Decentralized Memory Palace locked as v3.5+ feature** (decision row 26 below). A per-user git-backed structured knowledge store, selectively published over the OCM mesh with cryptographic signatures. Operates on the *human-readable knowledge artifact* axis — orthogonal to skill federation (compiled programs) and inference compute sharing (raw FLOPS). Reference implementation: Brand's existing OCR Memory Palace pattern, generalized from single-user to mesh-distributed with privacy controls. See [`../research/2026-05-09-decentralized-memory-palace-pattern.md`](../research/2026-05-09-decentralized-memory-palace-pattern.md) for the full architecture.

2. **Effective-Context Triad locked as cross-cutting design constraint** (decision row 27 below). Every OCM component must satisfy three properties simultaneously: **Expansion** (accessible corpus stacks across layers to GB-TB scale), **Stratification** (six explicit layers with their own retrieval policies + latency budgets), and **Quick Look-Up** (every layer respects its latency budget; expensive layers only invoke when cheap layers return low confidence). Frontier closed AI competes on expansion alone (1M-2M token windows); OCM competes on all three. This triad is the architectural justification for the Memory Palace addition and is measurable via Sandbox F in the frontier-comparison bench suite. See [`../research/2026-05-09-effective-context-triad-expansion-stratification-lookup.md`](../research/2026-05-09-effective-context-triad-expansion-stratification-lookup.md) for the full principle.

3. **Compression pipeline locked as canonical contract** (decision row 28 below). Compose-once / decompose-once across the layered stack: zstd-19 for at-rest palace markdown + Mem0 SQLite (~3-5× ratio), zstd-6 / brotli for wire-level mesh payloads (~60-80% bandwidth reduction), fp8 activation transfer for v6+ sharded inference (gated by Sandbox H confirmation). Names + locks the compression strategies already implicit in v0.4 (Mem0 library-driven retrieval = semantic compression; Aider repomap = structural compression; DSPy GEPA = behavioral compression; Q4_K_M = weight compression; RadixAttention = KV-cache deduplication). Any new feature that decompresses-recompresses-multiple-times is REJECTED as architectural violation.

4. **Encryption mapped onto privacy zones A/B/C** (decision row 29 below). Three threat models, three primitives: SQLCipher with Argon2id-derived key for Zone A (Mem0 at-rest); age + Ed25519 for Zone B (personal palace at-rest, signing); Ed25519 signatures (always) + age recipient encryption (when private-group share) for Zone C (mesh-published). Transport encryption already provided by iroh QUIC TLS 1.3. Honest limit: v6+ sharded inference is NOT privacy-preserving against a malicious borrowed-machine operator (TEE is hardware-gated; FHE is decade-out).

5. **Compress-then-encrypt order is mandatory** (decision row 30 below, also enforces canonical pipeline contract). Never the reverse — encrypted bytes are random by design. Length-leak padding (power-of-2 buckets) required for Zone C private group shares. Signatures over the wire-format (compressed-encrypted) bytes, not the plaintext.

OCM now has three structurally-aligned network-effect levers (v2+ inference sharing → v2+ skill federation → v3.5+ memory palace federation), all governed by the Effective-Context Triad and the Compress-then-Encrypt pipeline contract. See [`../research/2026-05-09-encryption-compression-optimizations.md`](../research/2026-05-09-encryption-compression-optimizations.md) for the full mapping.

## v0.3 revisions (2026-05-09)

Three changes from the memory + sub-context retrieval deep-dive research:

1. **Mem0 pick reaffirmed with stronger evidence.** Mem0 v3 hits 91.6 LoCoMo / 93.4 LongMemEval at ~7000 tokens/retrieval; library-driven retrieval (no agent decision required) is the directly-aligned pattern for the small-model thesis; OpenMemory MCP gives us local-first Ollama support out of the box. See decision row 9 below.
2. **DSPy GEPA upgraded from "opt-in extension" to "v2+ network-effect lever."** DSPy programs are first-class saveable artifacts (`program.save()/program.load()`). Signed compiled skills distributed across the OCM mesh are the directly-architected network-effect mechanism — every contributor's optimization improves every user's agent layer, with zero user-data privacy surface. This is OCM's actual federation play; **federated memory is deferred to v3+ research**, federated skills ship in v2. See decision row 23.
3. **MemoryArena added to verification plan.** Stanford's MemoryArena (2026) shows agents at near-100% on LoCoMo plummet to 40-60% on multi-session interdependent tasks. **OCM benchmarks both LoCoMo (recall) and MemoryArena (agentic utility), not just LoCoMo.** See verification plan.
4. **Sub-context retrieval techniques added to v1 stack** (new decisions): Aider-style repomap pattern as a generic compressed-view tool; Continue.dev's hybrid retrieval (LanceDB + ripgrep + LLM rerank) as the production blueprint for code context. See new decision rows 24-25.

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
| 9 | Agent memory + virtual context | **Mem0 v3 + OpenMemory MCP local mode** (was Letta in v0.1) | v0.3 reaffirmation with stronger evidence: Mem0 v3 hits **91.6 LoCoMo / 93.4 LongMemEval at ~7000 tokens/retrieval**; **library-driven retrieval** (no agent decision required) is structurally aligned with the small-model thesis (Letta's own engineering admits Llama 8B can't drive their tool-calling memory paradigm); **OpenMemory MCP** gives local-first Ollama support out of the box; 55.2k stars vs Letta's 22.5k |
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
| 23 | **DSPy GEPA + signed skill artifacts (v2+ network-effect lever)** | **DSPy GEPA-compiled skills distributed across the OCM mesh as signed, deterministic artifacts** (upgraded from "opt-in extension" in v0.2) | v0.3 strategic upgrade: `program.save()/program.load()` is first-class; compiled skills are deterministic, redistributable, privacy-clean (no user data leaks). **This is OCM's actual network-effect lever** — every contributor's optimization improves every user's agent layer. Federated memory is deferred to v3+ research; federated skills ship in v2. +10pp AIME, +17pp entity extraction with GEPA on small models |
| 24 | **Compressed-view tool (v1, new in v0.3)** | **Aider-style repomap pattern: NetworkX PageRank + tree-sitter compressed view** | Deterministic, no LLM call at retrieval time, fits any structured corpus (code / docs / conversation logs) into a configurable token budget; ideal for small models that lack the planning chops to navigate corpora. Repomix `--compress` (tree-sitter) cuts tokens ~70% while preserving structure |
| 25 | **Code-context retrieval (v1, new in v0.3)** | **Continue.dev's hybrid stack: LanceDB + ripgrep + LLM rerank, all local** | Production blueprint to lift wholesale; outperforms pure vector RAG; 100% local; privacy-clean. Adopt as the OCM code-context pattern when v1's MCP layer exposes code-aware tools |
| 26 | **Decentralized Memory Palace (v3.5+ network-effect lever, new in v0.4)** | **Per-user git-backed structured knowledge store, selectively published over the OCM mesh with cryptographic signatures**; substrate is git + markdown (GitHub for v3.5 hosting, iroh-blobs + git CRDT for v4+ pure-mesh); MCP tools `palace_search`/`read`/`write`/`publish`/`subscribe` expose the layer; three privacy zones (Zone A local Mem0 / Zone B personal palace / Zone C mesh-published) | OCM's third network-effect lever alongside inference sharing (v2+) and skill federation (v2+). Reference implementation: Brand's working OCR Memory Palace pattern, generalized from single-user to mesh-distributed. Full architecture in `../research/2026-05-09-decentralized-memory-palace-pattern.md`. Knowledge axis (human-readable curated artifacts) is orthogonal to skill federation (compiled DSPy programs) — they compound, do not duplicate |
| 27 | **Effective-Context Triad (cross-cutting constraint, new in v0.4)** | **Every OCM component must satisfy three properties simultaneously: EXPANSION (accessible corpus 5-50GB across layers, vs frontier's 1M-2M token single-call), STRATIFICATION (6 explicit layers with retrieval policies and latency budgets), QUICK LOOK-UP (each layer respects its latency budget; expensive layers only invoke when cheap layers return low confidence)** | The architectural triad that defines OCM's effective-context advantage over frontier closed AI. Justifies decision row 26 (Memory Palace federation) and the Sandbox F load-bearing measurement. Imposes engineering discipline on every future feature: a v3 reciprocity ledger that violates stratification by being on every-turn critical path is REJECTED; a v3.5 palace search that violates quick look-up by taking 10s for 5GB corpus is REJECTED; a v6 sharded inference that violates expansion by reducing accessible corpus is REJECTED. Full principle in `../research/2026-05-09-effective-context-triad-expansion-stratification-lookup.md` |
| 28 | **Compression pipeline contract (cross-cutting, new in v0.4)** | **At-rest: zstd-19 on palace markdown + Mem0 SQLite (sqlite-zstd VFS), ~3-5× ratio. Wire: zstd-6 / brotli on mesh payloads, ~60-80% bandwidth reduction. Activation transfer (v6+ sharded inference): fp8 default with fp16 fallback, gated by Sandbox H confirmation. Algorithmic compression already locked: Mem0 library-driven retrieval (semantic), Aider repomap (structural), DSPy GEPA (behavioral), Q4_K_M (weight), RadixAttention (KV-cache dedup), schema compression (token), Hermes XML (format). Pipeline contract: compress once at write-time, decompress once at consume-time; any new feature that decompresses-and-recompresses multiple times is architecturally REJECTED** | Compounds across the stack: full pipeline = ~670× compute compression vs naive fp16+stuff-everything baseline; ~75% bandwidth reduction on residential internet. Sandbox G measures wire compression; Sandbox H gates fp8 activation rollout. Full mapping in `../research/2026-05-09-encryption-compression-optimizations.md` |
| 29 | **Encryption mapped onto privacy zones A/B/C (new in v0.4)** | **Zone A (local Mem0): SQLCipher AES-256 with Argon2id-derived key from user passphrase (~5-15% latency overhead). Zone B (personal palace): age symmetric encryption + Ed25519 signing for at-rest; user identity keypair stored encrypted in OS secrets store (Keychain/DPAPI/libsecret). Zone C (mesh-published): Ed25519 signatures always; age recipient encryption when private group share (`mesh: group@<id>` frontmatter). Transport encryption already provided by iroh QUIC TLS 1.3. Honest limit: v6+ sharded inference is NOT privacy-preserving against malicious borrowed-machine operator (TEE hardware-gated; FHE decade-out)** | Sandbox I measures Mem0 encryption overhead. age chosen over GPG (5K LOC vs 250K, vastly easier to audit). Ed25519 signatures = ~50-100µs/op; age = ~50 MB/s; cryptographic overhead is sub-millisecond on KB-MB nodes — doesn't violate quick-look-up budgets. Full mapping in encryption-compression research note |
| 30 | **Compress-then-encrypt order mandatory (new in v0.4)** | **Pipeline contract: serialize → compress → encrypt → sign → transport. Reverse order is INVALID — encrypted bytes are random by design and post-encryption compression saves nothing. Length-leak padding (power-of-2 buckets: 128B/256B/512B/1KB/.../64KB) required for Zone C private group shares. Signatures over the wire-format bytes (compressed-encrypted), not the plaintext** | Standard cryptographic wisdom but explicitly locked because the order is load-bearing. Mitigates CRIME / BREACH-class attacks via padding. Simplifies skill-artifact verification (sign compressed bytes; if compression algorithm changes, re-sign) |
| 31 | **VM / cloud deployment policy (new in v0.5)** | **OCM v1 daemon runs on user-owned hardware by default. TWO supported remote-VM shapes: (a) bench/test fleets (now — Multipass single-host + cloud WAN fleets via Hetzner / DigitalOcean / Fly.io); (b) Phase 7+ relay/seed nodes (community-run, no user memory, like IPFS bootstrap). EXPLICITLY NOT SUPPORTED in v1: "OCM on a VPS for inference" as a sanctioned path. "Local-first" is redefined as "this user's compute" not "this user's physical machine"; users who deploy on a remote VM anyway must understand Zone A encryption stops being defense-in-depth and becomes load-bearing, and key custody requires an OS-keyring substitute (age + passphrase recommended). Sybil resistance (v5+) is a hard precondition for encouraging remote-VM peers in inference sharing or palace federation** | Names the policy that was implicit but unstated through v0.4. Bench fleet sandbox slot committed at `bench/isolation/mesh-transport/multipass-fleet/` (status INACTIVE until Phase 7 mesh transport). Honest non-recommendations also locked: don't optimize for VPS-as-primary-host (existing GPU-VPS providers do that better), don't run a public bootnet without v5 anti-abuse infrastructure, don't promise privacy guarantees that don't survive on a remote VM. Full reasoning in `../research/2026-05-09-remote-node-deployment.md` |
| 32 | **Bench-sandbox INACTIVE convention (new in v0.6)** | **Sandboxes that test future-tech hypotheses ship as slot-stubs with only `expected.json` (containing `"status": "INACTIVE"` plus `"blocked_on"` reasons) and `README.md`. The bench runner (`bench/bench/runner.py`) skips the docker-compose.yml + bench.py file requirement for INACTIVE sandboxes; ACTIVE sandboxes keep strict 4-file validation. Slot stubs commit the hypothesis contract early so when the underlying tech matures, the harness has a target without a fresh design pass.** | Locks the pattern after the multipass-fleet sandbox (PR #10) + 7 research-derived sandboxes (PR #20) shipped as INACTIVE. Closes the loophole that strict 4-file validation creates a "must implement everything before scaffolding anything" trap — disastrous for a solo project that needs to commit forward-looking bets cheaply. Counterargument considered: "but doesn't this dilute the bench's signal?" — no, because INACTIVE sandboxes don't pollute results (dry-run-all reports them separately); they only commit the hypothesis. Ten INACTIVE stubs cost ~30 minutes each and pre-load the verification surface for whoever picks up Phase 7+ (mesh), Phase 9+ (Memory Palace), or v6 (sharded inference) work |

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
7. **Long-context test** — 100K-token conversation that exceeds raw model context — Mem0 paging keeps it coherent
7b. **Memory recall benchmark — LoCoMo** — Mem0 v3 + Llama 3.1 8B Q4 hits ≥85% accuracy with avg ≤8000 tokens/retrieval (sandbox `mem0-v3-llama8b-locomo` per [bench sandbox additions plan](../plans/2026-05-09-bench-sandbox-additions-from-research.md))
7c. **Agentic memory utility — MemoryArena (Stanford 2026)** — Mem0 v3 + Llama 3.1 8B Q4 maintains ≥60% on multi-session interdependent tasks. **CRITICAL:** LoCoMo near-saturation does NOT prove the memory layer delivers useful agentic capability. MemoryArena is the honesty check that catches the LoCoMo→production gap (Stanford paper shows 40-60% drop on real interdependent tasks)
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
