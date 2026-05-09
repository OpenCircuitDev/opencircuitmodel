# OCM Tool Landscape — Synthesis of 4 Research Streams

**Date:** 2026-05-08
**Methodology:** Four independent research subagents, each with WebSearch/WebFetch, focused on a different layer of the OCM stack. Findings cross-validated where possible. Sincere uncertainty labeled.

This synthesis is the executive summary. The four full reports with citations are alongside this document:

1. [`2026-05-08-per-node-efficiency.md`](2026-05-08-per-node-efficiency.md) — inference engines, quantization, speculative decoding, MoE, Apple Silicon, hardware co-design
2. [`2026-05-08-mesh-distributed-compute.md`](2026-05-08-mesh-distributed-compute.md) — Petals/Exo/Bittensor, libp2p/iroh, reciprocity precedents, network-effect thresholds
3. [`2026-05-08-agent-memory-orchestration.md`](2026-05-08-agent-memory-orchestration.md) — Letta vs Mem0, agent frameworks, DSPy, MCP ecosystem, structured generation, tool-calling efficiency
4. [`2026-05-08-investment-market-viability.md`](2026-05-08-investment-market-viability.md) — comparable funding, grants, Bittensor lessons, network-effect data, solo-OSS sustainability, honest outcome distribution

---

## TL;DR — what changes about OCM

Six load-bearing changes from this research, ordered by magnitude of impact:

1. **Letta → Mem0 at the memory layer.** Letta's own engineering team admits Llama 8B-Instruct cannot reliably drive its tool-calling memory paradigm. Mem0's decoupled retrieval is the direct fix. Highest-ROI single change to the spec.

2. **Petals is dead → use Exo + Prima.cpp as v6 sharded-inference references.** Petals frozen at `transformers==4.43.1`, last release Sept 2023, infrastructure unreachable. Building on it is borrowing from a corpse.

3. **Canonical OCM model: Qwen3-30B-A3B MoE** (3.3B active / 30B total). Fits 24GB VRAM at Q4, hits 120-196 tok/s on RTX 4090, quality competes with dense 70B. The single best "small hardware, big quality" pick of the current generation.

4. **iroh > libp2p as v2 transport, with libp2p escape hatch.** libp2p's 70% NAT cliff (measured across 4.4M attempts, 85k networks) is the load-bearing risk. iroh's QUIC-native NAT traversal claims ~90% (vendor-stated) — even if real number is 80%, that's a 10-percentage-point delta on the most important variable.

5. **Add speculative decoding + Hermes tool format + schema compression as default inference behaviors.** Free 1.5-2.5× from EAGLE-3, +12-19pp tool-call accuracy from Hermes format, 30-60% token reduction from schema compression. None require model changes.

6. **Honest financial framing in README.** P50 outcome for OCM-as-described is "subsistence + mission" ($5-10K/mo blended, niche real users). P10 is burnout/archive at month 14 (50-60% likelihood). P90 is acquisition-with-team-retained (5-10% likelihood). Do not pitch as a financial play.

---

## Per-node efficiency — the math behind "fewer machines, more aggregate compute"

The headline finding: **stacking the right OSS pieces gets you ~20-30× aggregate per-node throughput vs naive vLLM-FP16-no-cache, plus another ~3× quality density from MoE**. That's roughly **80× quality-adjusted compute per machine**, decomposed:

| Layer | Multiplier | Confidence | Source |
|---|---|---|---|
| Q4 quantization (Q4_K_M / AWQ-INT4) | 2.0× | High | Independent benchmarks across Hugging Face / databasemart / oobabooga |
| Continuous batching at C=8 | 4.0× aggregate | High | vLLM / SGLang / TGI standard production |
| RadixAttention prefix-cache (shared OCM agent prompt) | 2.5× on top | Medium (range 2-4×) | LMSYS paper + independent Runpod / particula benchmarks |
| EAGLE-3 speculative decoding | 1.5× single / 1.3× concurrent | Medium | Independent reproductions; 4× academic numbers are temp=0 only |
| MoE swap (Qwen3-30B-A3B vs dense 30B equivalent) | 3× quality-density | Medium | Apxml + community benchmarks |
| **Cumulative** | **~20-30× aggregate, ~80× quality-adjusted** | — | — |

**Honest caveats from the per-node research:**
- The 80× quality-adjusted number is upper-bound. Promise users **15× aggregate, 25× quality-adjusted** to underdeliver high.
- 70B dense does NOT cleanly fit 24GB VRAM. Promise 30B-A3B MoE instead.
- 4× speculative decoding speedups are paper numbers at temp=0. Real chat workload is 1.5-2.5×.
- vLLM-class batching does not yet exist on Apple Silicon. Mac contributors are realistically single-user-at-a-time nodes.
- DeepSeek V3 is not a consumer mesh model. 1-3 tok/s with Unsloth 1.78-bit and offloading on 24GB.

**Recommended engine matrix:**

| Hardware profile | v1 ship | v2 upgrade | Explore later |
|---|---|---|---|
| RTX 4090 / 4060 | **vLLM + Q4 + APC + EAGLE-3** | **SGLang** for prefix-heavy users | TRT-LLM FP4 on 5090 |
| RTX 5090 | **TensorRT-LLM + FP4 + EAGLE-3** | SGLang FP4 once mature | Prefill-only role in mesh PD-disagg |
| M4 Pro (32GB+) | **MLX-LM + Q4** (single-stream) | MLC-LLM if batching matures | vllm-mlx if it stabilizes |
| M4 base / Mac Mini | **llama.cpp Metal + Q4** | MLX-LM swap if batching ships | BitNet 2B-8B as "tiny tier" |
| CPU-only / 8GB GPU | **llama.cpp + Q4 + 8B max** | BitNet b1.58 native ternary | Mamba-3 7B once quantized |

**Mesh-level architectural multipliers (v2-v6, not in single-node benchmarks):**
- **Prefill/decode disaggregation** — RTX 5090s do prefill (compute-bound, FP4), Mac Minis do decode (memory-bandwidth-rich, unified memory). Real 1.7× per Spheron. *This is OCM's single most interesting architectural multiplier.*
- **Tiered model fleet** — small fast model for easy turns, escalate to 30B-A3B for hard turns. 3-5× effective compute under realistic agent traffic.
- **Distributed speculative decoding** — draft on local fast node, verify on distant slower node. Proven 2-3× single-machine; not yet shipped on a mesh.

---

## Mesh layer — the landscape, not the rumor

**The two most important findings:**

1. **Petals is functionally dead.** transformers-version tombstone (`==4.43.1`, breaks on `>=4.50.0`), last release Sept 2023, health monitor unreachable when probed in May 2026. **Do not build on it.** Read the architectural patterns; ignore the codebase.

2. **The credible center of gravity is Prime Intellect / INTELLECT-2** (32B globally distributed RL training, May 2025, Apache 2.0, full code+weights+logs released). Even though it's training-not-inference, it's the most current real-world reference for "decentralized AI compute that actually shipped in 2025." Their `prime-RL` framework + TOPLOC verification + SHARDCAST weight broadcast are reference-quality.

**Other findings:**
- **Exo is alive but LAN-only** (44.4k stars, latest April 2026, mDNS discovery only). Take ergonomic patterns; don't inherit the LAN architecture.
- **Distributed Llama / Cake / Mesh-LLM** are hobby/research grade with bus-factor=1 risks.
- **Bittensor is financially active, technically narrow, operationally fragile.** $43M revenue against $2.77-3.4B market cap = mostly speculation. Subnet SN64 emissions:revenue ratio of 22:1 to 40:1 is the smoking gun. Don't tokenize OCM at v1.

**Transport layer verdict — iroh primary, libp2p escape hatch:**

| Property | libp2p | iroh |
|---|---|---|
| NAT traversal residential success | **70% ± 7.1%** (measured, 4.4M attempts, arxiv 2510.27500) | **~90%** (vendor-claimed, no third-party audit) |
| Production scale | 100k+ (IPFS) | 100k+ devices (vendor) |
| Single-vendor risk | Low | High (n0) |
| API ergonomics | Dense | Cleaner |

The 20-percentage-point NAT-success delta on residential consumer hardware is the single most important variable. iroh wins, with the `libp2p-iroh` bridge as a de-risking escape hatch.

**Reciprocity model — layered, no token at v1:**

| Year | Mechanism | Precedent |
|---|---|---|
| 0-1 | Folding@home pattern: status, leaderboard, cause-narrative, visible reciprocity ledger | F@h: 30k baseline + 1M COVID peak with no money |
| 1-2 | Storj-style time-cost + reputation: long vetting, signed certs | Storj v3: fixed real-money Sybil attack with this |
| 2-3 | Optional capital-stake + earned-credit reciprocity | Extends Storj+Filecoin lessons |
| 3+ (only if needed) | Token-as-incentive | Bittensor's lessons argue *against* this for Apache 2.0 community-first |

**Network-effect "alive" thresholds (empirical):**
- < 1,000 active nodes: survival mode (Hivemind, current Petals)
- 1k-10k: foundation tier (Tor ~8k relays)
- 10k-100k: mainstream-decentralized (Storj 22k, IPFS DHT estimate)
- 100k+: genuinely-mass (F@h COVID peak, BitTorrent)

OCM should target Folding@home's 30k baseline as the "made it" line. Below 1k is survival-mode; getting from 1k → 10k is the real work; getting to 30k+ requires a galvanizing event.

---

## Agent layer — the load-bearing finding

**The single most important finding from all four research streams:** Letta's own engineering blog explicitly admits that "Llama 8B-Instruct cannot reliably maintain a conversation alongside tool calling definitions" because Letta's paradigm requires the model to *interleave* conversation with `archival_memory_search` and `core_memory_replace` tool calls. **Letta is fundamentally designed around models smart enough to drive their own memory tools** — i.e., models that consumer hardware cannot run locally.

This directly contradicts OCM's "smaller models punch above their weight" thesis. **Mem0 fixes this** because retrieval is library-driven, not LLM-driven. The agent doesn't have to *decide* to retrieve; it just receives retrieved chunks. Decoupled architecture = small models work.

**Agent stack changes from this research:**

| Layer | Was (in spec) | Becomes | Why |
|---|---|---|---|
| Memory | Letta (or Mem0) | **Mem0** | Letta admits small-model failure; Mem0 v3 hits +20pp LoCoMo, +26pp LongMemEval; 55k stars, decoupled architecture |
| Agent runtime | LangGraph or Letta runtime | **Smolagents (CodeAct opt-in) + Letta-style ReAct fallback** | CodeAct: 30% fewer steps, 30% fewer LLM calls; LangGraph over-engineered for single-agent |
| Structured gen | Outlines + Instructor | **Instructor (user API) + engine-native (XGrammar/SGLang/llama.cpp grammar)** | 2-5× faster than Outlines as wrapper; Outlines stays as escape hatch for hard schemas |
| Optimization | (none) | **DSPy as opt-in `dspy.optimize_skill()` extension** | GEPA: +10pp AIME, +17pp entity extraction. Per-skill compile = power-user feature |
| Tool format | OpenAI JSON | **Hermes XML+JSON for small models, OpenAI for everything else (auto-detect)** | +12-19pp tool-call accuracy on Llama 8B / Mistral 7B |
| Action format | (implicit JSON) | **JSON default + CodeAct opt-in** | 50% latency cut, 60% token cut on representative workloads |
| Speculative decoding | (not mentioned) | **EAGLE-3 default-on** | Free 1.5-2.5× speedup |

**MCP is now table-stakes** (>500 public servers, native in Claude Code/Cursor/Windsurf/Zed/Cline/Continue.dev/JetBrains/ChatGPT/Gemini/OpenAI Agents SDK as of May 2026). Locking MCP in the OCM spec is correct and uncontroversial.

**Canonical model lineup (v1 release):**
- **Default (8GB+ VRAM):** Qwen3 8B Q4 / Llama 3.1 8B Q4
- **Recommended (24GB+ VRAM):** Qwen3-30B-A3B MoE Q4 — *the canonical OCM model*
- **Mac Mini base:** llama.cpp Metal + 8B Q4 (single-user)
- **CPU-only tier:** BitNet b1.58 2B
- **Workstation premium:** Qwen3-Coder-Next (3B active / 80B MoE) for coding agents

---

## Investment / market viability — the honest verdict

**Verdict: probably not financially viable; possibly mission-viable with right runway.**

Expected financial value of 18-24 months solo on OCM, against a $200-300K/yr AI-infra job, is approximately **-$70K to -$100K**. This is not a financially rational solo founder play in pure EV terms.

**Outcome distribution:**

| Outcome | Probability | What it means |
|---|---|---|
| **Burnout / archive** | 50-60% | Founder loses 18 months, learns a lot, returns to employment. README adds "looking for new maintainers." |
| **Niche subsistence** | 25-30% | Project lives, founder lives ($5-10K/mo blended), neither thrives. NLnet €30K + Sponsors $1-3K/mo + part-time consulting = subsistence-with-mission. |
| **Acquired/folded with team** | 10-15% | The llama.cpp outcome (Hugging Face, Feb 2026) — best-case-realistic. Autonomy + sustainability, not IPO. |
| **Foundation/open-core breakout** | 5-10% | Sustainable independent project, small team, $200K-$2M ARR, optional Series A. Requires luck + timing + executional excellence + galvanizing external event. |

**Key precedents:**
- **Petals never crossed escape velocity** despite working tech (most relevant comp)
- **Folding@home lost 99% of capacity post-COVID** — galvanizing events mobilize but don't sustain
- **Bittensor's $3B market cap is mostly speculation** — real revenue $3-15M, subnet subsidies 22-40:1
- **RunPod $120M ARR + 90% YoY** — *centralized* AI compute scales fast. Decentralized doesn't.
- **Tidelift survey:** 60% of OSS maintainers unpaid; 60% of solo maintainers considering quitting; 44% cite burnout
- **Median GitHub Sponsors monthly income: $50.** Caleb Porzio's $100K/yr is exceptional, not typical.
- **llama.cpp's HF acquisition (Feb 2026)** is the realistic best-case OSS exit — autonomy + sustainability, not IPO.

**The path that makes OCM viable:**

1. **Months 0-6: Foundation.** Ship v0.1 weekly. Build in public on Twitter/HN. **Apply NLnet first call (€20-50K).** Apply HF/Anthropic/OpenAI in-kind credits. Stand up GitHub Sponsors + Open Collective day 1. No token. No VC. **Checkpoint at month 6:** ≥1K stars + ≥30 active nodes + NLnet funded → continue. Else, reassess.

2. **Months 6-12: Traction.** Lean into one killer use case ("free personal AI agent with persistent memory") for the user pitch, separately from "share idle compute" for the contributor pitch. Grow user side faster than contributor side — contributors follow user demand. Apply Mozilla MIECO. Apply Astera Residency (long-shot transformational, $125-250K + GPU access + $1.5M project budget). Seek fiscal sponsorship (NumFOCUS or Open Collective) at $1K/mo donations.

3. **Months 12-18: Decision point.** P50 trajectory → find co-founder + open-core enterprise tier. P10 trajectory → graceful sunset, take a job at HF/Modal/RunPod/Together where OCM lives on as 20% project. P90 trajectory → choose between LF Agentic AI Foundation incubation vs. clean HF-style acquisition.

**Required preconditions for OCM to be viable:**
1. ≥18 months runway *independent* of OCM income (savings, partner income, contract work paying 50% time)
2. Killer year-1 demo moment that hits HN front-page within 90 days
3. NLnet grant secured by month 6
4. Acceptance that P50 is "subsistence + mission" — not founder wealth
5. A Year-3 exit plan with explicit checkpoint criteria

**Creative funding paths beyond the obvious:**
- **Mozilla Foundation $1M alternatives-to-AI-as-democracy-threat program (Dec 2025)** — explicit thesis match
- **Linux Foundation Agentic AI Foundation (Dec 2025, OpenAI/Anthropic/Block as founding)** — newly chartered, project incubation viable, legitimacy unlock
- **Astera Residency** — $125-250K + $1.5M project budget + GPU access — long-shot, transformational
- **DePIN backend partnership** (Akash/io.net/Render) for "share idle compute" — keeps OCM Apache-2.0 token-free while users opt-in to selling spare compute via third party
- **EU AI Act-aligned funding** — Horizon Europe / NGI Trust streams, €100-500K
- **Anthropic Economic Futures program** — explicit funding for projects exploring AI economic implications

---

## Things I refuse to promise (sincere underselling)

The four research streams converged on these promises being too aggressive:

| Don't promise | Promise instead |
|---|---|
| 70B dense on 24GB VRAM | Qwen3-30B-A3B MoE on 24GB |
| 4× speculative decoding | 1.5-2.5× realistic for chat |
| vLLM-class batching from a Mac | Single-user-at-a-time Mac contributor |
| DeepSeek V3 on consumer hardware | Workstation-tier (32GB+) only |
| 80% NAT traversal on residential | "We use iroh's QUIC-native traversal which substantially outperforms libp2p; benchmark in your network" |
| Bittensor-style passive income | Apache 2.0 + altruism + future earned-credit reciprocity |
| Founder income at viable launch | Subsistence + mission for solo path; co-founder + open-core for income |

---

## Sincerity audit (where evidence is thin)

- **iroh's 90% NAT-success claim** — vendor-stated, no third-party study
- **Bittensor revenue accounting** — $43M Q1 2026 figure contested
- **Petals worker count** — "near-zero" inferred from infra dead-letter, not measured directly
- **Exo throughput claim** — 2.2× on 3 devices is project-blog, no MLPerf-grade independent benchmark
- **The "1k alive threshold"** — synthesis from observation, not published threshold
- **Heterogeneous-device 5-50× latency gap to single-GPU** — workload-dependent
- **MLX-LM batching production-readiness in 2026** — trend says yes, no concrete benchmark proving it

If any of these become decision-load-bearing, run an independent measurement before committing.

---

## Source traceability

All citations are in the four full reports. Total of ~200+ unique sources spanning arXiv papers (15+), GitHub repos (40+), independent benchmark posts (30+), vendor blogs (20+), academic conference proceedings (SC/USENIX/ICLR), measurement studies (Protocol Labs NAT campaign, Tidelift OSS survey, OSS Funding Survey 2024), market data (Crunchbase, Messari, KuCoin, CoinGecko, Sacra), and historical project records (Folding@home, BitTorrent, Storj, Filecoin).
