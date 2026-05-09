# OCM v2+ Research Report: Distributed AI Mesh Stack

**Date:** 2026-05-08
**Prepared for:** OpenCircuitModel (OCM) — solo founder, Apache 2.0, 1K nodes / 10K users target in 18-24 months.
**Methodology:** Web research over GitHub repos, academic papers, vendor blogs, network telemetry dashboards, and crypto-research firm reports. Where data is thin, I label confidence explicitly. I tried to get hard numbers; I cite the source for each.

---

## 1. Distributed AI inference projects — current state

### 1.1 Petals (BigScience / Hugging Face / Yandex)

**Status: Zombie, leaning toward dead.** This is the single most important finding for OCM strategy.

- **Last release:** v2.2.0, **September 6, 2023** (ref: GitHub releases page). No tagged releases in 2024 or 2025.
- **Stars:** 10.1k (mature, but flat-curve).
- **Open issues:** 92, **20 PRs** that aren't being merged at any meaningful cadence.
- **Compatibility tombstone:** Petals strictly requires `transformers==4.43.1`. Updating to secure `transformers>=4.50.0` *breaks Petals*. That's a hard signal: nobody is doing the routine transformers-version chase that any real-world LLM lib has to do quarterly.
- **Network:** `health.petals.dev` was unreachable on my probe (ECONNREFUSED). The Petals home page itself shows "Oops, can't load the network status" in many captures. The most recent third-party measurements imply a small handful of bootstrap peers and limited active swarm.
- **Performance** (when alive): Llama-2-70B at ~6 tok/s single-batch, Falcon-180B at ~4 tok/s — these are 2023 numbers.

**What it does well:** The 2022-2023 Petals paper is still the reference architecture for "BitTorrent-style" pipeline-parallel LLM serving. Hivemind's DHT routing + RemoteSequenceManager for layer-shard discovery is genuinely good prior art. Worth reading.

**What it does poorly:** Single-batch latency ranges 1-5 seconds per token over WAN. No quantization-aware sharding. No production-grade reciprocity — workers were pure altruists.

**Confidence: HIGH** that Petals is functionally dormant. The transformers-version tombstone is dispositive.

### 1.2 Exo (exo-explore)

**Status: Very active, but pivoted away from internet mesh.** Critical re-positioning.

- **Stars:** 44.4k (massive). 2,329 commits.
- **Latest release:** v1.0.71, **April 23, 2026** — extremely current.
- **Architecture:** MLX backend (Apple Silicon-first), MLX-distributed for cluster comm. Ring-memory-weighted partitioning. Mixes CUDA / ROCm / Apple Metal in one cluster.
- **Throughput claim:** 2.2× speedup on 3 devices (multi-request throughput, near-linear).
- **Deployment focus:** Local cluster, automatic device discovery via mDNS. macOS app requires macOS Tahoe 26.2+.

**Critical answer to your direct question:** Exo is **LAN-first and effectively LAN-only as of 2026-05.** mDNS discovery doesn't work over the public internet. The MLX-distributed transport is a TCP mesh designed for low-latency local links. There is **no published roadmap for internet mesh.** Exo issue #848 ("Help Us Build the Future of Decentralized AI - From 1 Node to a Global Network") is a feature request, not a feature.

**What it does well:** Shipping. Real Apple Silicon perf. Heterogeneous-device sharding works today on a LAN. The team is aesthetically and technically credible.

**What it does poorly:** Not a mesh in any P2P sense. No reciprocity. No NAT traversal. No discovery beyond mDNS.

**Confidence: HIGH** based on direct repo inspection.

### 1.3 Distributed Llama (b4rtaz)

**Status: Active hobby/research project.**

- A C++ port of distributed inference, tensor parallelism over LAN Ethernet.
- Performance: requires high-bandwidth interconnect (Ethernet at minimum); depends linearly on link speed.
- Newer alternative — **prima.cpp** (BIT-BRICK) — uses a "Halda" scheduler that profiles compute, network, disk before scheduling. May 2025 publication.

**What it does well:** Tensor-parallel sharding on commodity Ethernet, llama.cpp-compatible.

**What it does poorly:** LAN-only. No reciprocity. Authoring quality is hobby-grade.

**Confidence: MEDIUM** — useful as reference impl, not a foundation to build on.

### 1.4 Cake (evilsocket)

**Status: Active solo project.**

- Rust + Candle, shards transformer blocks across iOS/Android/macOS/Linux/Windows.
- mDNS auto-clustering.
- Multimodal: text, image (SD/FLUX), TTS (VibeVoice).
- Self-described as "experimental code that's being actively developed and changed very quickly."

**What it does well:** Polyglot device support. Rust + Candle is a clean stack. Developer-velocity.

**What it does poorly:** Single-author project (bus factor = 1). LAN-mDNS only. No reciprocity. No NAT traversal that I can verify.

**Confidence: MEDIUM** — proof of concept, not infrastructure.

### 1.5 Bittensor (TAO)

**Status: Very active, financially. Technically narrow.**

- 50% subnet growth Q2 2025. ~$43M Q1 2026 revenue figure (per Coindesk; analysts dispute proportionality). Network projected to expand to 256 subnets by 2026.
- **December 2025 halving** cut emissions from 7,200 → 3,600 TAO/day.
- **dTAO (Q1 2025)** introduced per-subnet alpha tokens to reduce root-validator centralization.
- Grayscale GTAO Trust on NYSE (Jan 2026), spot ETF S-1 pending.

**Sustainability question (your direct ask):** Currently *speculative-leaning*. The Grayscale-cited gap between token inflation and confirmed external revenue is real. ~$43M revenue against a market cap historically ranging $1B-$5B+ is a P/S ratio in nosebleed territory. Lessons OCM should take: dTAO market-pricing of subnet contribution is genuinely good design. Lessons OCM should *avoid*: token-as-primary-incentive creates the validator-collusion failure mode (50% threshold, proven exploitable in practice — weight-copying validators, July 2024 PyPI supply-chain attack stealing $8M, May 2025 "runaway batch call" overload incident).

**Confidence: HIGH** on incidents and growth metrics; **MEDIUM** on whether subnet growth is real demand or token-farming.

### 1.6 Newer projects (2024-2026)

**Prime Intellect — INTELLECT-2 (May 2025).** First globally-distributed RL training run of a 32B model. Apache 2.0, full code+weights+logs released. Built on `prime-RL` async training framework with TOPLOC verification + SHARDCAST weight broadcast. **This is the most credible recent decentralized-AI engineering work I found.** Status: very active; the full pipeline (prime-RL, INTELLECT-2 model, training infra) is public.

**Hivemind (learning-at-home).** Still alpha (v0.8). Active issues, but Petals was its flagship downstream and Petals stalled. The DHT + DMoE primitives are useful library code; the project as a whole is research-grade.

**Gensyn.** Decentralized infrastructure, peer-to-peer comm, on-chain identity, cryptographic verification. Token-economic design. As of 2025 still pre-mainnet for general inference.

**LIME (Dec 2025).** Academic — collaborative LLM inference on memory-constrained edge devices, demonstrated on Jetsons. 1.7×-3.7× speedup vs SOTA. Useful technique reference.

**Hetis (SC 2025).** Heterogeneous GPU cluster serving with fine-grained dynamic parallelism. 1.49× latency reduction, 2.25× throughput.

**Bottom line for §1:** The space is *churning*. Petals — the canonical reference — is dead. Exo is alive but LAN-only. Prime Intellect is the credible new center of gravity for decentralized *training*; nobody owns decentralized *inference* at internet scale right now. **OCM's white space is real.**

---

## 2. Mesh transports

### 2.1 libp2p

- DCUtR baseline hole-punching success rate: **70% ± 7.1%** (4.4M attempts, 85k+ networks, 167 countries — arxiv 2510.27500, the 2025 Protocol Labs measurement campaign).
- Bias caveat from that paper: "volunteer participants from IPFS/libp2p communities may be more technically proficient and operate on more stable networks than the general population." Real residential-internet success may be lower.
- 97.6% of successful connections complete on first attempt (good).
- TCP and QUIC achieve similar success rates (~70%), upending older "UDP-only for NAT" wisdom.
- Multiple production deployments: IPFS, Filecoin, Polkadot, Eth2 consensus layer.

**What it does well:** Battle-tested at >100k node scale (IPFS). Multi-language (rust-libp2p, go-libp2p, js-libp2p). Modular transports.

**What it does poorly:** API surface is large and confusing. ~30% NAT traversal *failure* rate is the cliff that consumer P2P projects keep falling off. Bootstrap-node centralization in practice.

### 2.2 iroh (n0 / number0)

- Built on **noq** ("number 0 QUIC"), their own QUIC implementation with multipath + NAT traversal as a QUIC-level operation.
- Vendor claim: "roughly 9 out of 10 connections go direct" (≈90%).
- Deployed across "hundreds of thousands of devices already running iroh" (vendor claim — no third-party audit I found).
- Targeting v1.0 in 2025. As of search: 0.35+ public, with 1.0 prep underway. NoQ powers iroh since v0.96.
- Active 2024-2025 work to bridge into libp2p (`libp2p-iroh` crate adds iroh QUIC as libp2p transport).

**What it does well:** Modern (Rust + QUIC). Tailscale-inspired NAT traversal pattern (Wireguard/DERP-style relay fallback). Cleaner API than libp2p. Actively engineered for 2026, not maintained from 2018.

**What it does poorly:** No third-party benchmark of the 90% NAT-success claim. v1.0 not yet out. Smaller ecosystem than libp2p — fewer transports, fewer protocols, smaller community. Single-vendor risk (n0).

**Confidence: MEDIUM-HIGH** that iroh's NAT traversal genuinely outperforms libp2p; **LOW** on the precise 90% number until independently verified.

### 2.3 Veilid (Cult of the Dead Cow)

- Released Aug 2023 at DEF CON 31. Rust, runs on every major platform incl. WASM.
- Active 2024-2025 conference presence (HOPE XV, Security Fest 2025).
- VeilidChat ships, but no large-scale third-party deployment data.

**What it does well:** Strong privacy story. Onion-routing-by-default semantics. Cdc reputation = serious crypto people, not hype merchants.

**What it does poorly:** Tiny ecosystem. Privacy adds latency tax (multi-hop routing). Inappropriate for low-latency LLM inference shards. Documentation thin compared to libp2p/iroh.

**Confidence: MEDIUM.** Veilid is real but is the wrong tool for OCM's job (latency-sensitive inference traffic).

### 2.4 Holochain

- Agent-centric, not blockchain. Each user's chain + a shared DHT.
- Per academic papers (2025): 50ms publish, 30ms retrieve, 20 TPS single-node.
- Adoption challenges — DefiPlanet review (2025) explicitly: "lacks ... developer onboarding tools, documentation depth, and proven enterprise partnerships."

**What it does well:** Genuinely novel architecture. Some IoT use cases.

**What it does poorly:** Not built for inference traffic. Adoption is thin. Performance is application-class (TPS), not throughput-class (Gbps).

**Verdict:** Wrong fit for OCM.

### 2.5 WebRTC

- Browser-native, mature, well-supported.
- ICE/TURN gives 90%+ connection success but TURN traffic is *relayed*, not direct → throughput cap and TURN-server cost.
- LiveKit, Cloudflare R2, Twilio all use it. Production-ready.

**What it does well:** Browser support out-of-box. Rich tooling. Datachannel mode for arbitrary binary.

**What it does poorly:** TURN dependency at scale = either you pay for TURN, or you fail open. Native (non-browser) integration is awkward outside C++/JS.

### 2.6 Comparison synthesis

| Property | libp2p | iroh | veilid | holochain | webrtc |
|---|---|---|---|---|---|
| NAT traversal success (residential) | ~70% (measured) | ~90% (vendor) | ~unknown | ~unknown | 90%+ via TURN |
| Direct (no relay) | depends | ~90% claimed | privacy-routed | DHT | If P2P succeeds; else TURN |
| Production scale today | 100k+ nodes (IPFS) | 100k+ devices (vendor) | small | small | massive (browsers) |
| Native LLM-inference fit | medium | high | low (privacy tax) | low | medium |
| Single-vendor risk | low | high (n0) | medium | medium | low |
| API ergonomics | dense | cleaner | small surface | unique | familiar |

**Bottom line for §2:** For an LLM-inference mesh on residential consumer hardware, **iroh is the most aggressive bet** (clean stack, Tailscale-style NAT, native QUIC) and **libp2p is the conservative bet** (proven scale, language polyglot, but the 70% NAT cliff is the load-bearing problem).

**Confidence: HIGH** on libp2p numbers; **MEDIUM** on iroh until v1.0 + independent benchmark.

---

## 3. Reciprocity / "give to get" — what works

### 3.1 BitTorrent tit-for-tat

**Verdict: Partially survived adversaries; failure modes well-documented.**

- Original choke algorithm with optimistic unchoking is *robust* against ordinary free riders (per Feldman & Chuang 2005, Cohen 2003).
- BUT: Locher et al. ("Free Riding in BitTorrent is Cheap", HotNets 2006) and follow-ups demonstrate practical free-riding via the **Large View Exploit** (a peer maintains many connections, exploits optimistic unchoking, never reciprocates).
- Seeds are uniformly altruistic — no tit-for-tat applies post-completion. Most file availability over time depends on seed altruism, not enforced reciprocity.
- Measurement studies (Zghaibeh & Harmantzis) found free-rider population *increased over time* as users got smarter and bandwidth got cheaper.

**Lesson for OCM:** Naive tit-for-tat fails. Need a layered system that closes the optimistic-unchoke and large-view holes.

### 3.2 Storj

**Verdict: Hard-won lessons from real adversaries.** Most relevant precedent for OCM.

- **V2 failure (~2018-2019):** subsidizing nodes created exactly the Sybil incentive — "spin up many nodes to maximize baseline payout."
- **V3 fix:** Long initial vetting (months) + revocable signed leaf certificates + per-node certificate authority + escrow. Sybil attack now costs *time* (months of vetting per node) and *capital* (collateral).
- **Result:** 22,000+ active nodes, 103,000 holders peak in 2025, 7× revenue YoY (Sept 2025).

**Lesson for OCM:** **Time-cost** + **capital-cost** + **reputation-cost** combined. Pure reputation alone (no skin-in-the-game) is insufficient.

### 3.3 Filecoin

**Verdict: Cryptoeconomic pressure works; it's expensive to operate.**

- PoRep + PoSt: replicas tied to identities, time-locked. Sybil cost = compute + storage + collateral.
- 2025 trajectory: storage providers fell from ~3,000 to ~2,400 (Q2 2024) and continued to drop ~8% raw byte capacity Q1 2025; total stored data declined from 1,500 PiB → 1,300 PiB → 1,110 PiB (Q4 2024 → Q1 2025 → Q3 2025).
- **The decline is the lesson:** When token incentives cool, marginal providers exit. Reciprocity has to survive token-price volatility — Filecoin doesn't, fully.

**Lesson for OCM:** Token-only incentives concentrate marginal providers on token speculation. Use-value-driven reciprocity (give compute to get compute) is more shock-resistant.

### 3.4 Tor relay altruism

**Verdict: Genuinely altruistic, but small.**

- ~8,000 relays July 2025 (~2,500 exit, ~5,300 guard, ~2,000 bridges).
- Exit-relay count tripled over the past decade — slow, steady, bounded by altruism + legal risk.
- No tokenization. Foundation grants subsidize some operators.

**Lesson for OCM:** Pure altruism caps you in the thousands. To get to 1K-10K nodes you can probably skirt by on altruism + recognition; to go beyond, you need a real reciprocity mechanism.

### 3.5 Folding@home points / leaderboards

**Verdict: Recognition + competition works for a niche.**

- Pre-COVID: ~30,000 active users (March 2020).
- COVID peak: >1,000,000 active users (April 2020), 20× growth in 3 weeks. Aggregate compute exceeded the next 100 supercomputers combined; first to hit exaFLOPS.
- 2025 sustained: 12.9 native PFLOPS — a fraction of the COVID peak but still substantial.
- Driver: **status hierarchy** (PPD leaderboards), team competition (Linus Tech Tips, Reddit teams), social-cause framing.

**Lesson for OCM:** Non-monetary recognition + visible status hierarchy is genuinely powerful for the "first 100 contributors who don't get compute back" cold-start problem. Don't underrate this. Folding@home scaled to a million on points alone.

### 3.6 The cold-start dynamics ("first 100 contribute nothing back")

This is OCM's hardest problem, not a soluble one with a single trick.

- **Andrew Chen, "Cold Start Problem":** atomic-network MVN varies by product; 3 users for Slack, ~2k messages for stickiness, hyperlocal 2-sided marketplaces need much more.
- **F@h precedent:** 30k pre-COVID baseline survived for years on social-cause + leaderboards. That's your floor.
- **BitTorrent precedent:** seed altruism plus tit-for-tat — many torrents only stay alive because of seeds who *don't* benefit from tit-for-tat.
- **Hard truth:** Reciprocity systems break for the first cohort by definition. They contribute compute to *empty queues*. Some hybrid is required:
  1. Founder-subsidized compute pool (pay for AWS/Lambda, give first cohort *free model serving* in exchange for them running a node — non-economic value transfer).
  2. Recognition + leaderboard (cheap, F@h-validated).
  3. Future reciprocity guaranteed via earned-credit accumulation that activates once the network is alive.

**Bottom line for §3:** **Layered defense.** Reputation (slow to build, slow to lose) + capital stake (Sybil cost) + behavioral monitoring (catch large-view-style exploits) + non-monetary status (cold-start fuel). No single mechanism survives adversaries alone.

**Confidence: HIGH** on Storj/Filecoin lessons (well-documented); **HIGH** on F@h numbers (publicly logged).

---

## 4. Active-node count thresholds — the network-effect data

### 4.1 Folding@home

- Pre-COVID baseline: ~30,000 active users sustained through years of slow operation.
- COVID hockey-stick: **30k → 1M+ in ~3 weeks (April 2020)** = 33× growth.
- Trigger: external crisis + extensive media coverage + meaningful cause framing + a social/team-leaderboard mechanism that pre-existed and was ready to absorb the influx.
- Key infra reality: AWS, Microsoft Azure, Cisco, Oracle, VMware, Avast all *donated server-side scale* to absorb the influx. Without that, infrastructure would have collapsed. **Plan for influx is a real concern.**

### 4.2 IPFS

- ProbeLab (probelab.io/ipfskpi) is the canonical metrics dashboard.
- Order of magnitude: tens of thousands of DHT server nodes, hundreds of thousands of distinct peer IDs across gateways/clients.
- 2022 paper: a single measurement client connected to 40k-65k unique peer IDs.
- Trajectory: relatively stable since 2021-2022, neither boom nor bust. "Mature plateau" pattern.

### 4.3 Tor

- ~8,000 relays in 2025 (vs ~5,000 in 2015) = roughly +60% in a decade. Slow, steady.
- Exit relays: ~1.4k → ~2.8k 2021→2025 (2× in 4 years).
- Bridges declining slightly (~2.2k peak, ~2.0k now) — growth has shifted from count to capacity.

### 4.4 BitTorrent

- 170M MAU (2024 measurement). 2B installs lifetime (2020).
- BT traffic share of consumer internet: 35% (2004) → 2.91% (2022). Absolute peer count has remained large; share collapsed because everything else (video, cloud) grew faster.
- **DHT torrent dataset (2018-2024):** 28.6M unique torrents, 950M file-metadata records.

### 4.5 Petals

- Network effectively at zero or near-zero active workers as of 2025 based on health-monitor unreachability and the transformers-version freeze.

### 4.6 Empirical "alive" threshold

The data suggests an answer:

- **Below ~1,000 active nodes:** Project is in survival mode. Hivemind, early Holochain, current Petals. Token incentives decline → exit cascade.
- **1,000-10,000 active nodes:** Foundation tier. Niche-but-stable. Tor (~8k relays). Many Filecoin SP cohorts.
- **10,000-100,000 active nodes:** Mainstream-decentralized tier. Storj (22k), IPFS DHT-server estimate.
- **100,000+ nodes:** Genuinely-mass tier. F@h COVID peak. BitTorrent.

**Hockey-stick precedents:** F@h is the clearest case (3-week 33× growth) and required (a) external trigger, (b) pre-existing infra, (c) status hierarchy ready to absorb new users, (d) corporate-grade backstop infra. OCM should not plan to *cause* a hockey-stick — but should be *ready to absorb one* if AI-cost shock + privacy concern + frustration with proprietary inference creates one.

**Confidence: HIGH** on order-of-magnitude thresholds; **MEDIUM** on the exact "alive" cutoff.

---

## 5. Heterogeneous device sharding — research frontier

The key academic landscape:

- **Petals (2022):** Hivemind DHT routing for layer-shard discovery, RemoteSequenceManager pipelining. Foundational; performance dated.
- **Hivemind 2023+ work:** Decentralized Mixture of Experts (DMoE), fault-tolerant backprop, decentralized parameter averaging. Genuinely good library code but the upstream is alpha-status.
- **Hetis (SC 2025):** Heterogeneous GPU clusters, fine-grained dynamic parallelism, **1.49× latency reduction, 2.25× throughput vs SOTA heterogeneity-aware systems.** Strongest 2025 academic work.
- **LIME (Dec 2025):** Memory-constrained edge collaborative inference on Jetsons, 1.7×-3.7× speedup. Lossless under sporadic + bursty load. Good at the constrained-edge end.
- **CLONE (USENIX ATC 2025):** Customizes LLMs to per-device hardware profiles for latency-aware edge serving.
- **LIMINAL (2025):** Analytical performance model — abstracts apps as dependent operators (data volume, compute, sync) and hardware as compute/bandwidth/capacity/sync-delay. Useful for OCM scheduling design.
- **Mobile SoC heterogeneous LLM (2025):** Parallelizing GPU and NPU on the same SoC.

### Latency: fundamental vs improvable

The Petals paper (and follow-ups) decompose:

- **Fundamental:** Pipeline depth (number of stages) × per-stage compute time + autoregressive serial dependency. Cannot be eliminated for *single-batch* generation; can be partially hidden under high batch size.
- **Network-induced:** RTT × pipeline-depth. This is where the heterogeneous-device penalty lives. A residential network (~30-100ms RTT) over a 32-stage pipeline = 1-3 sec of pure network latency *per token* in the worst case.
- **Improvable:** (1) Pipelining (overlap compute and comm); (2) Speculative decoding across stages; (3) Larger batches (amortize network); (4) Smarter quantization-aware sharding to reduce activation transfer size.

**Concrete: A 70B model split into 32 stages over residential WAN with 50ms RTT cannot beat ~1.5 tok/s single-batch unless you change the autoregressive structure.** Multi-batch can hit 5-10× that. Speculative decoding can hit 2-3× more.

**Bottom line for §5:** Heterogeneous-device sharding is *productizable* but the gap to single-machine GPU inference will be 5-50× for single-batch. OCM should make peace with that. Throughput-oriented use cases (batch processing, async agents, code-review pipelines) > latency-oriented chat.

**Confidence: HIGH** on the fundamental-vs-improvable decomposition; **MEDIUM** on the exact 5-50× gap (workload-dependent).

---

## 6. The Bittensor question

**Tokenomics:**
- 21M hard cap, halving Dec 2025 (7,200 → 3,600/day emissions). Structurally Bitcoin-like in supply curve.
- dTAO (Q1 2025): per-subnet alpha tokens, market-priced subnet emissions.
- ~$43M Q1 2026 AI-usage revenue figure per Coindesk.

**Subnet structure:**
- ~125 subnets in 2025, projected 256 by 2026. Each subnet specializes (LLM inference, image gen, prediction markets, etc.).
- Validators stake → set weights on miners → emissions flow proportionally.

**Volume vs speculation:**
- Grayscale's own report flags the **gap between token inflation and confirmed external revenue.** That's an analyst from a *long* fund admitting the math is loose.
- $43M revenue is a real number, but versus a multi-billion market cap it's a P/S ratio that requires huge growth to justify.
- TAO's own price has been highly correlated with crypto cycles, not AI-revenue cycles. That tells you what the market actually prices.

**Adversary survival:**
- Yuma Consensus: "resistant to collusion of up to 50% of network weight" — but collusion *below* that threshold (weight-copying validators, lazy validators) was repeatedly demonstrated in 2024-2025.
- **Real incidents:** July 2024 PyPI malicious-package supply-chain attack ($8M stolen). May 2025 "runaway batch call" overload. These are operational failures, not consensus failures, but they're the kind of failure consumers actually experience.

**Lessons OCM should take:**
- dTAO market-pricing of contribution per subnet is genuinely good design — let *demand for compute* set the reward, not a flat distribution.
- Stake-as-credibility-filter (not stake-as-truth) is the right framing.
- 21M cap signal: don't inflate forever.

**Lessons OCM should avoid:**
- Token-as-primary-incentive ties OCM's mesh health to crypto cycles — bad idea for an Apache-2.0 community-first project.
- Heavy on-chain validation overhead (Bittensor's per-block weight-set + emissions is non-trivial in ops cost).
- Speculative-driven contributor influx tends to bring quality problems (Bittensor's "low-quality outputs" issue).

**Bottom line for §6:** Bittensor is **financially active, technically narrow, operationally fragile.** OCM should learn the dTAO market-pricing pattern and avoid the rest.

**Confidence: HIGH** on technical incidents; **MEDIUM** on long-term sustainability question (depends on whether AI revenue grows into market-cap, unknowable).

---

## 7. Creative / non-obvious mesh wins

These are **speculative-to-medium-confidence**, labeled accordingly.

### 7.1 Reservoir-style "warm-pool" reciprocity (speculative-MEDIUM)
Instead of measuring tit-for-tat *per-request*, treat reciprocity as a *bank balance* updated over hours/days. Contributors earn credit during their machine's idle time; spend credit during active use. Filecoin-collateral-like staking optional but not required. Solves the "first 100 contributors" problem partially because the *act of running* accumulates credit before any payoff is needed.

### 7.2 Bandwidth-aware shard placement (HIGH confidence — known-good idea, not yet productized)
Most heterogeneous schedulers are memory-aware (Exo's ring-memory partition) or compute-aware. Few are *bandwidth-aware*. For residential mesh, the bandwidth between two nodes dominates. Place adjacent pipeline stages on the *fastest residual link*. The LIMINAL 2025 model + Hetis 2025 work both point this direction. OCM could ship a measurable improvement here.

### 7.3 Speculative decoding across the mesh (HIGH confidence — known-good)
Run a small draft model on a fast local node, validate on a slower distant node. 2-3× speedup, well-established for single-machine inference. Distributing it (draft-locally, verify-remotely) is **not yet shipped** in any public mesh project I found. Real engineering opportunity.

### 7.4 Tailnet-as-mesh substrate (MEDIUM-HIGH)
Tailscale (or self-hosted Headscale) gives you NAT-traversal-99% and proper mesh routing for free. Build OCM on a Tailscale-style substrate (or use Tailscale directly via their Funnel/userspace API). The cost is single-vendor risk (Tailscale Inc.); the win is shipping a working mesh in *weeks* instead of solving NAT yourself. Iroh borrows their pattern, but Tailscale ships it.

### 7.5 Cross-mesh federation via libp2p adapter (LOW-MEDIUM, speculative)
Long-game: a libp2p adapter that lets OCM nodes *also* be reachable from IPFS / Filecoin / other libp2p meshes. Federated discovery, still own-mesh execution. Network-effect compounding.

### 7.6 GPU-as-cache pattern (MEDIUM, speculative)
Idle gaming GPU: serve KV-cache of recently-requested prefixes. Acts as a CDN for prefill, dramatically reducing first-token latency for popular prompts. Underexplored.

### 7.7 Personal-AI-first marketing (MEDIUM, brand-strategy)
The honest hook for the first 1k contributors isn't "earn money" or "save the world" — it's **"your friend who has a 4090 helps you when your M4 Mini is busy, and vice versa."** Trust networks (Discord servers, friend groups, gaming guilds) have built-in reciprocity already. Seed OCM in pre-existing trust networks, not in cold token-market discovery.

---

## Recommended mesh stack for OCM v2-v6

Ranked by my confidence in the recommendation:

### Inference layer: bet on **building from scratch, with Petals as reference and Exo as ergonomic inspiration**, not on either as a foundation.

**Reasoning:**
- **Petals is dead.** The transformers-version tombstone is dispositive. Building on a v2.2.0-frozen lib that breaks on `transformers>=4.50.0` is technical debt before you start.
- **Exo is alive but LAN-only.** Adopting Exo means inheriting a LAN architecture and re-doing the WAN/NAT/discovery layer yourself anyway. You'd be using Exo's *device discovery + sharding API* and replacing everything else. The leverage is real but smaller than it looks.
- **The right play:** Take the *Petals architectural patterns* (Hivemind DHT routing for layer-shard discovery, sequence-manager pipelining) + the *Exo ergonomic patterns* (mDNS-style auto-discovery on LAN as fallback, ring-memory weighted partitioning, MLX backend on Mac) + a fresh transport layer. Read the prime-RL/INTELLECT-2 codebase as a current-decade reference for how to do TOPLOC-style verification of work product.
- **If you need a single dependency:** Use Hivemind's DHT primitives (the library, not Petals on top of it) for shard discovery. They're alpha but functional and the abstractions are correct.

**If forced to pick Petals vs Exo:** **Exo, no question.** It ships, it's maintained, the team is alive. But understand you're picking an *ingredient*, not a finished system.

**Confidence: HIGH** on this recommendation.

### Transport layer: bet on **iroh (primary)** with **libp2p (fallback / federation)**

**Reasoning:**
- The 70% NAT cliff is the biggest single risk to OCM's "consumer mesh" thesis. If 30% of users can't connect peer-to-peer, your cold-start network is worse than 70% of its size — much worse, because *both ends* of every potential connection have to succeed.
- Iroh's bet on QUIC NAT traversal as a first-class operation + Tailscale-style relay fallback is the right architectural bet for 2026. The vendor's "9-of-10 direct" claim is plausibly true; even if it's actually 80%, that's substantially above libp2p's 70%.
- Risk: iroh is single-vendor (n0). Mitigate via the `libp2p-iroh` bridge — keep your application protocols layered above libp2p semantics so you can swap transports if n0 disappears.
- Don't pick veilid (privacy-tax wrong fit), holochain (wrong domain), or pure WebRTC (TURN-cost trap at scale).

**If forced to pick libp2p vs iroh:** **iroh, with a libp2p escape hatch.** The 20-percentage-point NAT-success delta is the single most important real-world variable.

**Confidence: MEDIUM-HIGH.** I'd want one more independent benchmark of iroh under residential load before committing fully — but the architectural argument is strong even without it.

### Reciprocity layer: **layered, non-monetary first, optional monetary later**

**Recommendation, backed by precedent:**

1. **Year 0-1: Folding@home pattern.** Status + leaderboard + cause-narrative + visible reciprocity ledger ("you helped X, you've been helped Y times"). This got F@h to 30k baseline and 1M peak with no money. Precedent: HIGH confidence.

2. **Year 1-2: Storj-style time-cost + reputation.** Long vetting period + signed certs to make Sybil cost real. *No token.* Just identity + history. Precedent: HIGH confidence (Storj fixed a real-money attack with this).

3. **Year 2-3: Optional capital-stake + earned-credit reciprocity.** Earned-credit accumulates on idle contribution, spent on active use. *Optional* small staking for higher-tier compute (priority queues, reserved bandwidth). No token. Precedent: speculative, but extends Storj+Filecoin lessons.

4. **Year 3+, only if needed: token-as-incentive.** And only if the use-value reciprocity has hit a ceiling. Bittensor's lessons are: 50% collusion threshold, supply-chain attacks against client packages, low-quality outputs from speculative-driven miners. Don't go here lightly.

**Explicit historical precedent:** Storj's V2→V3 transition (subsidies → vetting+collateral). Folding@home's 30k baseline on points alone. BitTorrent's seed-altruism reality. None of these used a token at the v1 milestone you (OCM) are at. The "Apache 2.0, solo founder" identity is exactly right for the F@h-pattern start. Add monetary incentive only if it's actually needed.

**Confidence: HIGH** on the layered-defense pattern; **MEDIUM** on the "no token v1" call (defensible from precedent but not certain).

---

## Where evidence is thin (sincerity audit)

- **iroh's 90% NAT-success claim:** vendor-stated, no third-party study. Likely directionally correct, exact number unverified.
- **Bittensor revenue accounting:** $43M Q1 2026 figure is reported but contested re: how much is real external demand vs. token-recycling.
- **Petals worker count:** infrastructure unreachable when probed; "near-zero" is inferred from the maintainer-version tombstone + dead infra, not measured directly.
- **Exo throughput claim:** 2.2× on 3 devices is from the project blog; no MLPerf-grade independent benchmark.
- **The "alive threshold" of 1,000 nodes:** my synthesis from observation, not a published threshold.
- **F@h COVID hockey-stick generalization:** that was an external-shock-driven event; expecting OCM to be able to *trigger* one is hopeful at best.
- **Heterogeneous-device 5-50× latency gap to single-GPU:** workload-dependent; the 50× upper end is residential-WAN single-batch, the 5× lower end is high-batch with speculative decoding.

If any of those numbers are decision-load-bearing, run an independent measurement before committing.

---

## Sources

- [GitHub - bigscience-workshop/petals](https://github.com/bigscience-workshop/petals)
- [Petals – Run LLMs at home, BitTorrent-style](https://petals.dev/)
- [Petals: A Step Towards Decentralized AI - DEV Community](https://dev.to/gssakash/petals-a-step-towards-decentralized-ai-4op9)
- [Petals: Collaborative Inference and Fine-tuning of Large Models (paper)](https://huggingface.co/papers/2209.01188)
- [Petals Health Monitor](https://health.petals.dev/)
- [GitHub - exo-explore/exo](https://github.com/exo-explore/exo)
- [Transparent Benchmarks - 12 days of EXO](https://blog.exolabs.net/day-1/)
- [Deep Dive: Exo — Distributed AI Inference on Consumer Hardware](https://medium.com/@leif.markthaler/deep-dive-exo-distributed-ai-inference-on-consumer-hardware-068e341d8e3c)
- [Help Us Build the Future of Decentralized AI - Issue #848](https://github.com/exo-explore/exo/issues/848)
- [Exo Project Status - Issue #819](https://github.com/exo-explore/exo/issues/819)
- [GitHub - b4rtaz/distributed-llama](https://github.com/b4rtaz/distributed-llama)
- [GitHub - evilsocket/cake](https://github.com/evilsocket/cake)
- [Cake: A Rust Framework for Distributed Inference - MarkTechPost](https://www.marktechpost.com/2024/07/22/cake-a-rust-framework-for-distributed-inference-of-large-models-like-llama3-based-on-candle/)
- [Running LLM with Distributed Inference using prima.cpp on K1 Cluster](https://www.bit-brick.com/2025/05/08/running-llm-with-distributed-inference-using-prima-cpp-on-k1-cluster/)
- [Distributed Inference with vLLM](https://blog.vllm.ai/2025/02/17/distributed-inference.html)
- [GitHub - learning-at-home/hivemind](https://github.com/learning-at-home/hivemind)
- [INTELLECT-2: The First Globally Distributed RL Training of a 32B Model](https://www.primeintellect.ai/blog/intellect-2)
- [INTELLECT-2 paper (arxiv 2505.07291)](https://arxiv.org/abs/2505.07291)
- [State-of-the-art in Decentralized Training - Prime Intellect](https://www.primeintellect.ai/blog/our-approach-to-decentralized-training)
- [Bittensor (TAO) Network Status - Coindesk Sept 2025](https://www.coindesk.com/business/2025/09/13/bittensor-ecosystem-surges-with-subnet-expansion-institutional-access)
- [Bittensor on the Eve of the First Halving - Grayscale](https://research.grayscale.com/reports/bittensor-on-the-eve-of-the-first-halving)
- [Bittensor Protocol: A Critical and Empirical Analysis](https://arxiv.org/html/2507.02951v1)
- [Bittensor whitepaper](https://bittensor.com/whitepaper)
- [Subnets · taostats](https://taostats.io/subnets)
- [Comparing Iroh & Libp2p - Iroh blog](https://www.iroh.computer/blog/comparing-iroh-and-libp2p)
- [iroh on QUIC Multipath](https://www.iroh.computer/blog/iroh-on-QUIC-multipath)
- [iroh 1.0 roadmap](https://www.iroh.computer/roadmap)
- [noq, noq, who's there? - Iroh](https://www.iroh.computer/blog/noq-announcement)
- [GitHub - n0-computer/iroh](https://github.com/n0-computer/iroh)
- [Challenging Tribal Knowledge: Decentralized NAT Traversal Measurement (arxiv 2510.27500)](https://arxiv.org/html/2510.27500v1)
- [DCUtR - libp2p docs](https://libp2p.io/docs/dcutr/)
- [Hole Punching - libp2p](https://libp2p.io/docs/hole-punching/)
- [Decentralized NAT Hole-Punching Measurement Campaign discussion](https://discuss.libp2p.io/t/decentralized-nat-hole-punching-measurement-campaign/1616)
- [Decentralized Hole Punching - Marten Seemann (Protocol Labs)](https://research.protocol.ai/publications/decentralized-hole-punching/seemann2022.pdf)
- [Veilid](https://veilid.com/)
- [Veilid - Wikipedia](https://en.wikipedia.org/wiki/Veilid)
- [Spritely and Veilid - EFF](https://www.eff.org/deeplinks/2023/12/meet-spritely-and-veilid)
- [Holochain](https://www.holochain.org/)
- [Can Holochain Replace Traditional Blockchains? 2025 Review](https://defi-planet.medium.com/can-holochain-replace-traditional-blockchains-reviewing-its-agent-centric-approach-in-2025-bf48fd9f6483)
- [Among the DLTs: Holochain for IoT (PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC12251913/)
- [Free Riding in BitTorrent and Countermeasures (Moor MA thesis)](https://pub.tik.ee.ethz.ch/students/2006-So/MA-2006-26.pdf)
- [Free Riding in BitTorrent is Cheap - HotNets 2006](http://conferences.sigcomm.org/hotnets/2006/locher06free.pdf)
- [Revisiting free riding and the Tit-for-Tat in BitTorrent](https://link.springer.com/article/10.1007/s12083-008-0013-7)
- [Free-Riding on BitTorrent-like P2P File Sharing Systems](https://www.cse.fau.edu/~jie/TPDS-Modeling%20Analysis%20and%20Improvement%20for%20Free-Riding%20on%20BitTorrent-like%20File%20Sharing%20Systems-1.pdf)
- [Storj v3 whitepaper](https://static.storj.io/storjv3.pdf)
- [Decentralized cloud storage with blockchain: Filecoin, Storj, IPFS](https://medium.com/@naeemulhaq/decentralized-cloud-storage-with-blockchain-a-technical-comparison-of-filecoin-storj-and-ipfs-e455f7a7d42b)
- [SoK: Decentralized Storage Network](https://eprint.iacr.org/2024/258.pdf)
- [Storj Statistics 2025 - CoinLaw](https://coinlaw.io/decentralized-storage-statistics/)
- [State of Filecoin Q1 2025 - Messari](https://messari.io/report/state-of-filecoin-q1-2025)
- [State of Filecoin Q3 2025 - Messari](https://messari.io/report/state-of-filecoin-q3-2025)
- [Folding@home Statistics](https://stats.foldingathome.org/)
- [Folding@home: Achievements from over twenty years of citizen science (PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC10055475/)
- [2020 in Review - Folding@home](https://foldingathome.org/2021/01/05/2020-in-review-and-happy-new-year-2021/)
- [Folding@home - Wikipedia](https://en.wikipedia.org/wiki/Folding@home)
- [The Cold Start Problem (Andrew Chen)](https://www.amazon.com/Cold-Start-Problem-Andrew-Chen/dp/0062969749)
- [Network effect - Wikipedia](https://en.wikipedia.org/wiki/Network_effect)
- [Tor Statistics 2026 - SQ Magazine](https://sqmagazine.co.uk/tor-statistics/)
- [Tor Network Statistics: A Decade of Growth (Glukhov 2025)](https://www.glukhov.org/post/2025/10/tor-statistics/)
- [Welcome to Tor Metrics](https://metrics.torproject.org/)
- [Tor Servers - Tor Metrics](https://metrics.torproject.org/networksize.html)
- [BitTorrent Statistics 2024 - EarthWeb](https://earthweb.com/bittorrent-statistics/)
- [BitTorrent - Wikipedia](https://en.wikipedia.org/wiki/BitTorrent)
- [BitTorrent is No Longer the King of Upstream Internet Traffic - TorrentFreak](https://torrentfreak.com/bittorrent-is-no-longer-the-king-of-upstream-internet-traffic-240315/)
- [Mapping the Interplanetary Filesystem (arxiv 2002.07747)](https://arxiv.org/pdf/2002.07747)
- [Passively Measuring IPFS Churn and Network Size (arxiv 2205.14927)](https://arxiv.org/pdf/2205.14927)
- [Measuring the IPFS network](https://docs.ipfs.tech/concepts/measuring/)
- [Hetis: Serving LLMs in Heterogeneous GPU Clusters (SC 2025)](https://dl.acm.org/doi/10.1145/3712285.3759784)
- [LIME: Collaborative Lossless LLM Inference on Edge Devices (arxiv 2512.21835)](https://www.arxiv.org/abs/2512.21835)
- [Customizing LLMs for Latency-Aware Edge Inference (USENIX ATC 2025)](https://www.usenix.org/system/files/atc25-tian.pdf)
- [Efficient LLM Inference: Bandwidth, Compute, Synchronization (arxiv 2507.14397)](https://arxiv.org/html/2507.14397v1)
- [Characterizing Mobile SoC for Heterogeneous LLM Inference](https://dl.acm.org/doi/pdf/10.1145/3731569.3764808)
- [Distributed Inference of Large Language Models on Edge Devices (ICSCA 2025)](https://dl.acm.org/doi/10.1145/3731806.3731859)
- [Sybil in the Haystack: Blockchain Consensus & Sybil Resistance](https://www.mdpi.com/1999-4893/16/1/34)
- [Alternative Sybil Resistance Methods (Roughgarden FoB '21)](https://timroughgarden.github.io/fob21/reports/r3.pdf)

---

**Word count: ~3,300 words.**
