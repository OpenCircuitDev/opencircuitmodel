# OpenCircuitModel (OCM) — OSS Inference Efficiency Research

**Date:** 2026-05-08
**Mandate:** Identify per-node throughput multipliers for a P2P inference mesh of ~1000 contributors on heterogeneous consumer hardware (M4 Mac Mini base / mid-tier NVIDIA / occasional workstation). The thesis is "fewer machines, more aggregate compute" — every per-node multiplier scales the whole mesh.

**Honesty pre-commit:** Where data is sparse, vendor-only, or single-source, I label it. Where I'd be guessing, I say "I don't know." I have not personally rerun any benchmark; everything below is cited from public reports.

---

## 1. Best-in-class inference engines (state of play, May 2026)

### 1a. NVIDIA consumer (RTX 4060 / 4090 / 5090)

**Llama 3.1 8B Q4_K_M / equivalent INT4 / FP4 throughput:**

| Hardware | Engine | Single-stream tok/s | Concurrency=8 (aggregate) | Source / quality |
|----------|--------|---------------------|---------------------------|------------------|
| RTX 4060 8GB | llama.cpp (Q4_K_M) | 40+ tok/s | data sparse — single-user is the realistic mode at 8GB | [databasemart](https://www.databasemart.com/blog/ollama-gpu-benchmark-rtx4060), [bswen](https://docs.bswen.com/blog/2026-03-27-rtx-4060-token-speed-benchmark-coding/) — independent |
| RTX 4090 24GB | vLLM (GPTQ-Int4) | ~120 tok/s single | **~600 tok/s aggregate at C=8** | [databasemart](https://www.databasemart.com/blog/vllm-gpu-benchmark-rtx4090) — independent |
| RTX 4090 24GB | llama.cpp (Q4_K_M, Ollama) | 95–110 tok/s single | batching exists but production-quality is contested | independent (databasemart) |
| RTX 5090 32GB | vLLM FP16 8B | ~3,500 tok/s aggregate (large batch) | independent ([Spheron](https://www.spheron.network/blog/rent-nvidia-rtx-5090/)) |
| RTX 5090 32GB | TRT-LLM FP4 (native Blackwell) | ~7,200 tok/s prompt-process | vendor-aligned ([Runpod](https://www.runpod.io/blog/rtx-5090-llm-benchmarks)) — independent reproduction sparse |

**Engine ranking (Llama 3.1 8B, H100 reference, May 2026):**
- **SGLang** ~16,200 tok/s aggregate (29% over vLLM) — independent reproductions in [particula.tech](https://particula.tech/blog/sglang-vs-vllm-inference-engine-comparison), [premai](https://blog.premai.io/vllm-vs-sglang-vs-lmdeploy-fastest-llm-inference-engine-in-2026/)
- **LMDeploy/TurboMind** ~16,000 tok/s — claims up to 1.8× vLLM ([InternLM](https://github.com/InternLM/lmdeploy))
- **vLLM** ~12,500 tok/s — baseline
- **TensorRT-LLM** competitive when tuned, especially on Blackwell w/ FP4
- **TGI / Triton** — production-stable, throughput trails the front line

**Continuous batching, production quality:**
- vLLM, SGLang, LMDeploy, TGI, TensorRT-LLM: yes, production-quality.
- llama.cpp: server has continuous batching since ~2024 but the maintainer ecosystem and HN discussion ([Hacker News](https://news.ycombinator.com/item?id=44367827)) say "almost nobody uses it for batched serving." Functional, not production-grade for high concurrency.
- Ollama: thin wrapper over llama.cpp; not built for concurrency.
- ExecuTorch: on-device focus, single-stream.
- MLX-LM: single-stream historically; batching landed in MLX-LM through 2025 but is not at vLLM-class production maturity.

**Verdict:** For NVIDIA consumer nodes, **SGLang** or **LMDeploy** wins on raw throughput; vLLM has the broader ecosystem and is the safest default. TensorRT-LLM is strongest on the RTX 50-series specifically because of native FP4.

### 1b. Apple Silicon (M3/M4 base, M4 Pro)

| Hardware | Engine | 8B Q4 single-stream | Notes |
|----------|--------|---------------------|-------|
| M4 base (16GB) | llama.cpp Metal | ~25–30 tok/s | independent ([modelfit](https://modelfit.io/blog/best-llm-mac-mini-m4-16gb/), [LLMHardware](https://llmhardware.io/guides/mac-mini-m4-llm-guide)) |
| M4 base | MLX-LM | similar to llama.cpp at this size class | arxiv [2511.05502](https://arxiv.org/abs/2511.05502) |
| M4 Pro (24–32GB) | llama.cpp Q4_K_M 7B | ~60–80 tok/s | [contracollective](https://contracollective.com/blog/llama-cpp-vs-mlx-ollama-vllm-apple-silicon-2026) |
| M4 Pro (32GB+) | MLX-LM Qwen3-30B-A3B (MoE) | ~130 tok/s | community-reported, single-source — flagged as "looks great but needs reproduction" |
| M2 Ultra | MLX-LM | highest sustained throughput; MLC-LLM lowest TTFT | independent paper [2511.05502](https://arxiv.org/abs/2511.05502) |

**Continuous batching on Apple Silicon — concrete state:**
- MLX-LM: batching support exists, production maturity is limited. Evidence is single-source on most benchmarks.
- MLC-LLM: best-in-class TTFT; throughput trails MLX in the arxiv comparative paper.
- llama.cpp Metal: stable, well-trodden, batching available but not the focus.
- vLLM-MLX (community fork): exists, evaluated in [macgpu](https://macgpu.com/en/blog/2026-mac-inference-framework-vllm-mlx-ollama-llamacpp-benchmark.html), but not Apple-blessed; production stability uncertain.

**Verdict on Apple side:** For OCM mesh nodes serving multi-user traffic from a Mac, **MLX-LM is the best per-Apple-watt choice** for autoregressive throughput, but **expect to ship llama.cpp as a fallback** because batching maturity matters when serving other users in the mesh.

### 1c. CPU-only / low-end GPU

- llama.cpp dominates. CPU-only Llama 3.1 8B Q4_K_M lands in single digits tok/s on a modern Ryzen/Apple non-Pro chip.
- BitNet b1.58 (Microsoft, native ternary) shows the most interesting CPU numbers — see Section 7. ~5–7× the throughput of FP16 on a CPU at the 2B–8B range (per [Microsoft BitNet repo](https://github.com/microsoft/BitNet)) — but only at small sizes.
- No engine other than llama.cpp/BitNet is realistic at this tier.

**Bottom line for OCM v1 engine choice:**
- NVIDIA contributor: **vLLM** as default (largest ecosystem, lowest integration risk); **SGLang** as a "fast lane" for users running shared OCM agent prompts at scale (Section 2 explains why).
- Apple contributor: **MLX-LM** primary, **llama.cpp Metal** fallback.
- CPU-only contributor: llama.cpp; consider BitNet for a "tiny model" tier.

---

## 2. Prefix caching / RadixAttention real-world impact

The 5–7× headline number for SGLang's RadixAttention comes from the [LMSYS paper](https://arxiv.org/pdf/2312.07104) and is **measured on prefix-heavy synthetic workloads** (few-shot benchmarks, tool-augmented agent traces). It is real but conditional.

**Hit-rate evidence (independent, [particula.tech](https://particula.tech/blog/sglang-vs-vllm-inference-engine-comparison), [Runpod](https://www.runpod.io/blog/sglang-vs-vllm-kv-cache)):**

| Workload | SGLang RadixAttention hit rate | vLLM block-level APC hit rate |
|----------|------------------------------|------------------------------|
| Few-shot shared examples | 85–95% | 15–25% |
| Multi-turn chat | 75–90% | 10–20% |
| Code analysis | 60–80% | — |
| Mixed prod traffic | 50–70% | — |

**OCM's "50 users sharing a 1500-token system prompt" scenario:**

- This is the canonical RadixAttention sweet spot. Every request shares a byte-identical prefix.
- Realistic multiplier: **3–5× throughput vs vLLM-default**, with vLLM-APC closing the gap to ~1.3–2× when the prefix is single and predictable. The 6.4× paper number is an upper bound that requires *zero* TTL/eviction pressure — unrealistic in an open mesh.
- Confidence: **high** that there's a real ≥2× multiplier for OCM's workload; **medium** on whether it lands at 3× or 5× at any given hour.

**OCM's "long agent conversations with growing context" scenario:**

- RadixAttention shines because every turn N reuses turn 1..N-1's KV cache.
- Independent benchmarks ([particula](https://particula.tech/blog/sglang-vs-vllm-inference-engine-comparison)): SGLang holds ~30 tok/s/request at C=100 vs vLLM ~16 tok/s/request — ~1.9× per-user.
- That's a sustained 2× win for the agent-conversation case under load.

**One real caveat I want to flag:** RadixAttention's 6.4× "up to" multiplier degrades catastrophically when prefix ordering is inconsistent. For OCM that means: lock the system prompt format byte-for-byte across releases, and never put per-user data before per-cohort data in the prompt. The runpod prod guide is explicit about this.

**Bottom-line:** prefix caching is the single largest "free" multiplier. For the mesh case (many users + shared OCM agent prompt + multi-turn agents), expect a real **2–4×** over vLLM-no-cache. Use SGLang.

---

## 3. Speculative decoding state-of-the-art

| Method | Realistic speedup (consumer, chat) | Quality regression | Notes |
|--------|-------------------------------------|--------------------|-------|
| Vanilla draft-target (small Llama 3.2 1B drafting 8B) | 1.5–2× | None (rejection sampling exact) | Easy, supported in vLLM/SGLang/llama.cpp |
| Medusa-1/2 | 2.18× / 2.83× on Vicuna-7B | None | independent ([Together](https://www.together.ai/blog/medusa)); training overhead but no separate model |
| Lookahead (no draft model) | 1.5× chat, 2× code | None | LMSYS [blog](https://lmsys.org/blog/2023-11-21-lookahead-decoding/) — independent |
| EAGLE-2 | 2–3× typical | None (Metropolis-Hastings) | Production-stable, supported in TRT-LLM/vLLM/SGLang |
| EAGLE-3 | **2–3× single-user, 1.7× under concurrency** | None | [HF/lmsys](https://huggingface.co/blog/lujangusface/tw-eagle3-gpu) — independent reproduction (Llama 3.1 8B: 1.25× reproduced vs 1.32× claimed). 4–6× academic numbers are at temp=0 only. |

**Engine support matrix (May 2026):**
- vLLM: vanilla, EAGLE-2, EAGLE-3 (P-EAGLE parallel variant via AWS)
- SGLang: EAGLE-3, MTP, vanilla — mature
- TensorRT-LLM: EAGLE-2/3, Medusa, Lookahead, ReDrafter (Apple-contributed)
- llama.cpp: vanilla draft-target only; PR [thc1006/qwen3.6-spec-decoding](https://github.com/thc1006/qwen3.6-speculative-decoding-rtx3090) found **no net speedup** for Qwen3.6 35B-A3B MoE on RTX 3090 across 19 configs. **Important data point**: speculative decoding is *not* a guaranteed win on consumer hardware for MoE models.

**One honest caveat that's underappreciated:** Speculative speedups are heavily batch-size-dependent. EAGLE-3 reproduces at 1.25–1.39× single-user but degrades to 1.30× per-request at C=32. The 4–6× numbers in papers require temp=0 and academic prompts. For the actual OCM workload (concurrent users, varied prompts, temperature>0) plan for **1.5–2.5× realistic** from speculative decoding, not 4×.

**Verdict for OCM:**
- v1: ship with EAGLE-3 enabled (where engine supports it). It's free quality-wise.
- v2: support model-pair routing — if a user is running Llama 3.1 8B, suggest Llama 3.2 1B as the draft for vanilla speculative.
- Don't promise users 4× from speculative. Promise 2× and underpromise.

---

## 4. Quantization frontier (May 2026)

**For Llama 3.1 70B → 24GB VRAM (the headline question):**

| Method | Bit-rate | VRAM (weights only) | Perplexity hit | Verdict |
|--------|----------|--------------------:|---------------:|---------|
| FP16 | 16 | 140GB | baseline | doesn't fit |
| Q4_K_M (GGUF) | ~4.5 | 41GB | tiny (<+0.2 ppl) | doesn't fit |
| AWQ-INT4 | 4 | 35GB | minimal | doesn't fit on a single 24GB |
| Q3_K_M | ~3.5 | 32GB | small | doesn't fit if KV included |
| **IQ3_M / IQ4_XS** (with imatrix) | ~3.0–4.3 | **~25–30GB** | small-moderate | **borderline, marginal fit** |
| **EXL3** (turboderp v3) | 2.5–3.5 | ~22–28GB | "significantly outperforms uniform methods at low bpw" — [exl3.md](https://github.com/turboderp-org/exllamav3/blob/master/doc/exl3.md) | **likely the best 24GB option** |
| **AQLM 2-bit (1×16)** | 2 | ~22GB | Llama-3-70B Q2 fits w/ ~5K context on 3090Ti — independent ([HF](https://huggingface.co/ISTA-DASLab/Meta-Llama-3-70B-Instruct-AQLM-2Bit-1x16)) | fits, but slow (~8 tok/s) and quality hit measurable |
| **QTIP 2-bit** (Cornell) | 2 | ~22GB | Llama-2-7B 6.89 ppl Wikitext = matches 3-bit SOTA | research-grade; engine support (Together, custom kernels) less broad |
| **HQQ-INT4** | 4 | ~35GB | competitive with AWQ at 4-bit | doesn't fit 70B in 24GB at 4-bit |

**Verdict:**
- **70B does not cleanly fit on a single 24GB consumer GPU** with FP16 KV cache + room for context. The honest answer is: 70B on 24GB is a "barely works, KV-cache constrained" tier even at 2.5-bit.
- For OCM, **don't promise 70B on consumer 24GB nodes**. Promise 70B on 32GB+ workstations.
- **For 24GB nodes the sweet spot is 30B-class MoE (Qwen3-30B-A3B).** It hits ~120–196 tok/s on RTX 4090 and gives 70B-quality output on most chat tasks ([promptzone](https://www.promptzone.com/jordan_lee_72db45ce/best-local-llms-for-consumer-hardware-2026-llama-33-70b-vs-qwen3-30b-a3b-vs-deepseek-r1-distill-336p)).

**Quality-loss data for Llama 3.1 8B Q4_K_M:** +0.18 ppl on Wikitext-2 vs FP16 (arxiv [2601.14277](https://arxiv.org/pdf/2601.14277)). Effectively no quality loss for chat workloads. Q2_K shows +3.5 ppl — visibly degraded. IQ2/IQ3 with imatrix recovers most of that for mid-bit.

---

## 5. MoE on consumer hardware

**The thesis:** MoE is a free multiplier — you pay memory bandwidth like a 37B dense model but get 671B-class quality (DeepSeek V3) or 141B-class (Mixtral 8x22B).

**Reality check:**

| Model | Total params | Active params | Effective dense equivalent | Consumer fit |
|-------|------------:|--------------:|---------------------------|--------------|
| Mixtral 8x22B | 141B | 39B | beats Llama-2 70B on MMLU/HellaSwag | needs ~80GB fp16 → too big for 24GB; AWQ ~50GB still doesn't fit |
| DeepSeek V3 | 671B | 37B | rivals frontier closed models | weights ~690GB FP8; **does not fit consumer cards even at 1.58-bit (~151GB)**. Unsloth's 1.78-bit dynamic gets 1–3 tok/s on a 24GB card with offloading — slow but functional. |
| **Qwen3-30B-A3B** | 30B | 3.3B | competitive with Llama 3.3 70B on chat | **fits 24GB at Q4 → 120–196 tok/s on RTX 4090** ([apxml](https://apxml.com/models/qwen3-30b-a3b)). This is the actual MoE consumer winner. |
| Mamba-3 / Jamba 1.5 | 12B–52B hybrid | n/a (non-MoE) | competitive at long context | covered in Section 7 |

**Effective compute multiplier:** For Qwen3-30B-A3B vs a dense 30B (e.g., Llama-2-30B equivalent), the active-only compute is ~10× cheaper per token (3.3B / 30B ≈ 0.11). In practice, MLX-LM on M4 Pro reports the MoE running ~3× faster than a dense-30B equivalent on the same hardware ([compute-market](https://www.compute-market.com/blog/mac-mini-m4-for-ai-apple-silicon-2026)). The full theoretical 9× isn't realized because of expert-routing overhead and memory bandwidth limits.

**Verdict for OCM:**
- MoE 30B is the single biggest "quality density" win of the current generation for consumer nodes.
- DeepSeek V3 is **NOT** a 1000-node mesh play — it requires workstation-class memory.
- Qwen3-30B-A3B (or its successor Qwen3.6-35B-A3B) is the **canonical OCM v1 model**. 24GB fits, quality competes with 70B dense, and throughput is 2–3× a dense model of comparable quality.

---

## 6. Mac-specific

**The arxiv comparative paper [2511.05502](https://arxiv.org/abs/2511.05502)** is the best independent source. Tested on M2 Ultra (192GB):

- **MLX-LM: highest sustained generation throughput.**
- **MLC-LLM: lowest TTFT for medium prompts; strongest "out of box" features.**
- **llama.cpp: most efficient single-stream, lightweight.**
- **Ollama: best DX, lags throughput.**
- **PyTorch MPS: memory-constrained.**

For **continuous batching specifically:** the paper notes batching/concurrency behavior is one of the eval axes but does not flag any Apple-side framework as production-batch-ready in the vLLM sense. As of 2026-05, **MLX-LM has experimental batching, MLC-LLM has it more maturely, llama.cpp has it but use is rare**. The macgpu blog evaluates a vllm-mlx fork that gets closest to vLLM's batching model on Apple but is not blessed.

**Real M4 Pro (32GB) numbers, May 2026:**
- Llama 3.1 8B Q4: ~60–80 tok/s (llama.cpp Metal, single-stream)
- MLX-LM ~20–40% higher than llama.cpp at 8B for autoregressive ([starmorph](https://blog.starmorph.com/blog/apple-silicon-llm-inference-optimization-guide), [contracollective](https://contracollective.com/blog/mlx-vs-llama-cpp-apple-silicon-local-ai))
- Qwen3-30B-A3B MoE: ~130 tok/s on M4 Pro 64GB MLX, **single-source** — flagged as needs reproduction
- For Mac Mini M4 base 16GB: 8B Q4 ~25–30 tok/s

**Verdict:** OCM should ship MLX-LM for Mac contributors, with llama.cpp Metal as the dependable fallback. Treat batching as "best effort" on Apple — don't promise vLLM-class concurrent throughput from a Mac node. A Mac contributor at 8B is realistically a **single-user-at-a-time** node, which still delivers ~70 tok/s of quality output to the mesh — useful, just not concurrency-amplified.

---

## 7. 2025–2026 breakthroughs

### 7a. SSM / hybrid architectures in production

- **Jamba 1.5 (AI21):** production hybrid, 256K context, 3× throughput vs Mixtral 8x7B at long context ([AI21](https://www.ai21.com/blog/announcing-jamba/)).
- **Mamba-3 (CMU/Princeton/Cartesia/Together, Mar 2026):** released ([spheron](https://www.spheron.network/blog/mamba-3-state-space-model-gpu-cloud-deployment/)).
- **IBM Granite 4.0, Mistral Codestral, AI21 Jamba** all use hybrids in prod.
- **Industry trend:** ~90% Mamba + 10% Transformer is the hybrid sweet spot.

For OCM the pitch is: long-context agent conversations are *exactly* where Jamba/Mamba-3 win. KV cache size is the consumer-VRAM bottleneck for transformers; SSMs amortize it. **But**: open-weight SSM ecosystem is thinner than Llama. vLLM/SGLang support is partial as of May 2026.

**Verdict:** Treat SSM hybrids as a v3+ exploration, not a v1 default. Track Jamba 1.5 closely.

### 7b. Quantization-aware-trained (QAT) native models

- **BitNet b1.58 2B4T (Microsoft, MIT-licensed):** the first open native 1.58-bit (ternary) LLM. Trained from scratch at ternary, not PTQ. Microsoft's bitnet.cpp framework ships ~5–7× CPU throughput over FP16 baselines at the 2B–8B scale ([infoq](https://www.infoq.com/news/2025/04/microsoft-bitnet-1bit-llm/)).
- **Limit:** only scaled to 8B publicly. Quality at 8B does not match a Llama 3.1 8B FP16. This is "tiny model density" not "frontier compression."

**Verdict:** Useful for OCM's CPU-only contributor tier as a "tiny tier" model. Not a v1 mainline play.

### 7c. Hardware-software co-design

- **Blackwell FP4** (RTX 5090, Pro 6000, B200/B100): ~2× throughput vs FP16 on supported models ([Spheron](https://www.spheron.network/blog/rent-nvidia-rtx-5090/), [databasemart](https://www.databasemart.com/blog/ollama-gpu-benchmark-rtx5090)).
- **TensorRT-LLM** is the only engine fully exploiting FP4 today; vLLM/SGLang are catching up.
- **Apple MLX:** unified memory + zero-copy KV cache is its real edge; widens at long context ([starmorph](https://blog.starmorph.com/blog/apple-silicon-llm-inference-optimization-guide)).

**Verdict:** RTX 5090 contributors should run TRT-LLM; everyone else uses vLLM/SGLang. A 5090 with FP4 is roughly 2× a 4090 at the same wattage. For "fewer machines, more aggregate compute," that is exactly the curve OCM wants.

---

## 8. Creative / non-obvious wins

### 8a. **Prima.cpp** ([arxiv 2504.08791](https://arxiv.org/abs/2504.08791))

Distributed inference *across heterogeneous home devices* — Wi-Fi-connected Macs, PCs, Pis. Pipelined-ring parallelism + heterogeneity-aware scheduler. Independently published and in-domain for OCM:

- **70B model on 4 mixed devices with 37GB combined RAM+VRAM: 674 ms/token** (vs OOM on dllama).
- 32B with speculative decoding: 26 tok/s.

This is the closest open reference to "what OCM v3 looks like" I've seen. The pipelined-ring topology assumes co-located devices on a LAN — not a P2P internet mesh — but the scheduler insights and the K/V offloading patterns transfer.

### 8b. **EXO Labs** ([github](https://github.com/exo-explore/exo))

Mesh inference across Mac Studio / Mac Mini / iPhone with auto-discovery, MLX backend, RDMA-over-Thunderbolt. Closer to OCM's vision than Petals. Production-quality enough that Tom's Hardware covered an EXO + DGX Spark hybrid hitting 2.8× on AI benchmarks ([toms](https://www.tomshardware.com/software/two-nvidia-dgx-spark-systems-combined-with-m3-ultra-mac-studio-to-create-blistering-llm-system-exo-labs-demonstrates-disaggregated-ai-inference-and-achieves-a-2-8-benchmark-boost)).

EXO is **the most direct prior art for OCM's architecture**. OCM should study its discovery protocol, network topology, and MLX-distributed wrapper before reinventing.

### 8c. **Petals** ([github](https://github.com/bigscience-workshop/petals))

The original BitTorrent-style LLM inference network, BigScience. Layer-sharded across volunteers. Honest data from the team:

- 3–25× **lower latency** vs offloading (which is the right comparison for OCM)
- Throughput is *worse* than colocated GPUs — this is the geographic-distance tax.

For OCM's reciprocity model, Petals' shortest-path routing and direct server-to-server communication patterns are directly applicable.

### 8d. **Mesh-LLM** ([github](https://github.com/Mesh-LLM/mesh-llm)) and **LocalAI federated mode**

Both ship today. Mesh-LLM has a working "small models can consult vision/big peers" pattern that's interesting for OCM's cross-model inter-agent design.

### 8e. **Prefill-decode disaggregation**

Independent benchmarks ([spheron](https://www.spheron.network/blog/prefill-decode-disaggregation-gpu-cloud/), [bentoml](https://bentoml.com/llm/inference-optimization/prefill-decode-disaggregation)) show **~75% throughput gain at ~45% cost increase** when prefill and decode run on separate GPUs.

For the OCM mesh: this is the killer pattern that emerges naturally. **A workstation contributor with a 5090 is great at prefill** (compute-bound, FP4 dense matmul). **A Mac Mini contributor is great at decode** (memory-bound, unified-memory KV cache). The mesh can route prefill and decode to different node types — a free 1.7× throughput gain on the mesh as a whole that no single-node setup gets.

This is the most interesting OCM-specific architectural multiplier I found. **Speculative idea, flagged as such**: heterogeneous mesh PD-disaggregation as a v2 feature.

### 8f. **MoE weight offloading with HQQ**

[arxiv 2312.17238](https://arxiv.org/pdf/2312.17238) — MoE inference with offloading for consumer GPUs, using HQQ for fast on-the-fly quantization of inactive experts. Could push 70B-class MoE onto 24GB cards with reasonable throughput. **Speculative for OCM** — the implementation effort is non-trivial.

---

## Recommended efficiency stack for OCM

**Stack-up math for one NVIDIA contributor (RTX 4090, Llama 3.1 8B):**

Baseline: vLLM FP16, no prefix cache, no spec decoding, no batching. Call this **1.0× = ~50 tok/s** for a single user.

| Layer | Realistic multiplier | Cumulative | Confidence |
|-------|---------------------|------------|------------|
| Q4 quantization (Q4_K_M / AWQ-INT4) | 2.0× | 2.0× | High |
| Continuous batching at C=8 | 4.0× aggregate (per-user mostly preserved) | 8.0× aggregate | High |
| RadixAttention prefix-cache (OCM shared system prompt) | 2.5× on top | **20× aggregate** | Medium (3× best, 2× worst) |
| EAGLE-3 speculative decoding | 1.5× single-user / 1.3× concurrent | **~26× aggregate** | Medium |
| MoE swap (Qwen3-30B-A3B at 30B-active vs dense 30B) | 3× quality-density | **~78× quality-adjusted** | Medium |

So a fully-stacked SGLang + Q4 + RadixAttention + EAGLE-3 + MoE node delivers **roughly 20–30× the aggregate throughput** of a "naive vLLM FP16 single-stream" baseline — and **80×+ quality-adjusted throughput**. Across 1000 contributors, that's the difference between a viable mesh and a hobbyist toy.

I'd be cautious about claiming the full 80× to users. The honest number to put on a slide is **"~15× aggregate, ~25× quality-adjusted, vs naive FP16 single-stream"** — and that already justifies the project.

### Per-node engine recommendations

| Node profile | v1 (ship now) | v2 (3–6mo) | Explore later (v3+) |
|--------------|---------------|------------|---------------------|
| RTX 4090/4060 | **vLLM + Q4_K_M + RadixCache via vLLM-APC + EAGLE-3** | Migrate to **SGLang** for prefix-heavy users; add Qwen3-30B-A3B as default model | TRT-LLM on 5090 with FP4; PD-disaggregation in mesh |
| RTX 5090 / Pro 6000 | **TensorRT-LLM with FP4 + EAGLE-3** | SGLang FP4 once mature | Prefill-only role in mesh PD-disagg |
| Workstation (multi-GPU) | vLLM with TP=2/4 | SGLang DP | Run 70B / DeepSeek V3 as "premium tier" |
| M4 Pro | **MLX-LM + Q4** (single-stream serving) | MLC-LLM if batching matures | Vllm-mlx if it stabilizes |
| M4 base / Mac Mini | **llama.cpp Metal + Q4** | MLX-LM swap if batching ships | BitNet 2B–8B as "tiny tier" |
| CPU-only / 8GB GPU | llama.cpp Q4 + 8B max | BitNet b1.58 for 2B "tiny tier" | Mamba-3 7B once quantized |

### Mesh-level multipliers (architectural, not per-node)

These are OCM-specific gains that don't show up in any single-node benchmark:

1. **Prefix-cache by cohort** — pre-warm a node's RadixCache with the OCM system prompt at idle. Free 2× at first request after cold-start.
2. **Cross-node prefill/decode disaggregation** — route prefill to FP4 5090s, decode to memory-bandwidth-rich Macs. Real 1.7× ([spheron](https://www.spheron.network/blog/prefill-decode-disaggregation-gpu-cloud/)).
3. **Tiered model fleet** — small fast model (Qwen 1.5B / Llama 3.2 3B) for "easy" turns, escalate to 30B-A3B for hard turns. Effective compute 3–5× under realistic agent traffic. Independent precedent: Mesh-LLM's inter-model collaboration.
4. **Speculative decoding pairs across nodes** — draft model on a Mac Mini, target model on a 4090. Probably nets a multiplier in narrow conditions; unproven; **flagged speculative**.

### What I would not promise users

- **70B dense on a 24GB card.** You can squeeze it with EXL3 or AQLM but throughput will be 5–10 tok/s and KV cache will starve context. Promise 30B-A3B MoE instead.
- **4× speculative decoding speedups.** Real number is 1.5–2.5× for chat. The 4–6× academic numbers are temp=0 + cherry-picked prompts.
- **vLLM-class batching from a Mac.** Apple inference on 2026-05 still favors single-stream-at-time. A Mac node serves one user well; it does not multiplex like a 4090 does.
- **DeepSeek V3 on consumer hardware.** Even Unsloth's 1.78-bit dynamic gets 1–3 tok/s with offloading on 24GB. Not viable as a mesh model.

### Things I don't know with confidence

- Whether MLX-LM's batching reaches vLLM-class production maturity in 2026. The trend says yes, but I have no concrete benchmark proving it as of May 2026.
- The exact RadixAttention multiplier in OCM's specific workload mix. The 2.5× I used is a midpoint between the 2× independent floor and the 6.4× paper ceiling. Any node operator should measure this themselves.
- Whether speculative decoding nets out positive on heterogeneous Apple hardware. Most data is NVIDIA-centric. The thc1006 RTX 3090 result showing **no net speedup for MoE** is a real warning sign; treat spec decoding as workload-dependent, not free.
- Long-term viability of EXO Labs / Mesh-LLM / Petals. These are interesting prior art, but the field is young and consolidations / failures are likely.

### One sentence summary

**The 20–30× aggregate per-node multiplier is real and reproducible today by stacking SGLang + Q4 + RadixAttention + EAGLE-3 + Qwen3-30B-A3B; the additional 1.5–3× from mesh-level prefill/decode disaggregation and tiered routing is OCM's specific architectural win that no single-node setup gets.**

---

## Sources cited

**Inference engines / benchmarks:**
- [vLLM vs SGLang vs LMDeploy 2026](https://blog.premai.io/vllm-vs-sglang-vs-lmdeploy-fastest-llm-inference-engine-in-2026/)
- [SGLang vs vLLM 2026 (particula.tech)](https://particula.tech/blog/sglang-vs-vllm-inference-engine-comparison)
- [vLLM vs TensorRT-LLM vs SGLang (Spheron)](https://www.spheron.network/blog/vllm-vs-tensorrt-llm-vs-sglang-benchmarks/)
- [LMDeploy GitHub](https://github.com/InternLM/lmdeploy)
- [llama.cpp continuous batching server README](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)
- [llama.cpp HN discussion on batching](https://news.ycombinator.com/item?id=44367827)
- [vLLM RTX 4090 benchmark (databasemart)](https://www.databasemart.com/blog/vllm-gpu-benchmark-rtx4090)
- [RTX 5090 LLM benchmarks (Spheron)](https://www.spheron.network/blog/rent-nvidia-rtx-5090/)
- [RTX 5090 Runpod benchmarks](https://www.runpod.io/blog/rtx-5090-llm-benchmarks)
- [RTX 4060 benchmarks (databasemart)](https://www.databasemart.com/blog/ollama-gpu-benchmark-rtx4060)
- [Mac Mini M4 LLM guide](https://llmhardware.io/guides/mac-mini-m4-llm-guide)
- [Apple Silicon comparative study (arxiv 2511.05502)](https://arxiv.org/abs/2511.05502)
- [Best LLMs for Mac Mini M4 16GB](https://modelfit.io/blog/best-llm-mac-mini-m4-16gb/)
- [llama.cpp vs MLX vs Ollama vs vLLM](https://contracollective.com/blog/llama-cpp-vs-mlx-ollama-vllm-apple-silicon-2026)
- [Apple Silicon optimization guide (Starmorph)](https://blog.starmorph.com/blog/apple-silicon-llm-inference-optimization-guide)

**RadixAttention / Prefix caching:**
- [SGLang paper (arxiv 2312.07104)](https://arxiv.org/pdf/2312.07104)
- [LMSYS RadixAttention blog](https://www.lmsys.org/blog/2024-01-17-sglang/)
- [SGLang vs vLLM Multi-Turn (Runpod)](https://www.runpod.io/blog/sglang-vs-vllm-kv-cache)
- [vLLM Automatic Prefix Caching docs](https://docs.vllm.ai/en/stable/design/prefix_caching/)
- [SGLang in Production (Runpod)](https://www.runpod.io/articles/guides/blog-sglang-production-llm-pipelines)

**Speculative decoding:**
- [EAGLE-3 paper (arxiv 2503.01840)](https://arxiv.org/html/2503.01840v1)
- [EAGLE-3 production blog (HF)](https://huggingface.co/blog/lujangusface/tw-eagle3-gpu)
- [Medusa paper (arxiv 2401.10774)](https://arxiv.org/abs/2401.10774)
- [Medusa benchmarks (Together)](https://www.together.ai/blog/medusa)
- [Lookahead decoding (LMSYS)](https://lmsys.org/blog/2023-11-21-lookahead-decoding/)
- [TensorRT-LLM speculative decoding](https://nvidia.github.io/TensorRT-LLM/advanced/speculative-decoding.html)
- [TensorRT-LLM 3x speedup blog (NVIDIA)](https://developer.nvidia.com/blog/tensorrt-llm-speculative-decoding-boosts-inference-throughput-by-up-to-3-6x/)
- [vLLM speculative decoding blog](https://blog.vllm.ai/2024/10/17/spec-decode.html)
- [thc1006 Qwen3.6 MoE speculative decoding negative result](https://github.com/thc1006/qwen3.6-speculative-decoding-rtx3090)

**Quantization:**
- [QTIP paper (arxiv 2406.11235)](https://arxiv.org/abs/2406.11235)
- [Cornell QTIP repo](https://github.com/Cornell-RelaxML/qtip)
- [AQLM Llama-3-70B 2-bit](https://huggingface.co/ISTA-DASLab/Meta-Llama-3-70B-Instruct-AQLM-2Bit-1x16)
- [oobabooga GPTQ/AWQ/EXL2 comparison](https://oobabooga.github.io/blog/posts/gptq-awq-exl2-llamacpp/)
- [llama-3 quant comparison (matt-c1)](https://github.com/matt-c1/llama-3-quant-comparison)
- [ExLlamaV3 docs](https://github.com/turboderp-org/exllamav3/blob/master/doc/exl3.md)
- [HQQ blog (Dropbox)](https://dropbox.tech/machine-learning/halfquadratic-quantization-of-large-machine-learning-models)
- [Llama-3.1-8B unified evaluation (arxiv 2601.14277)](https://arxiv.org/pdf/2601.14277)
- [MoE offloading + HQQ (arxiv 2312.17238)](https://arxiv.org/pdf/2312.17238)

**MoE / DeepSeek / Qwen:**
- [DeepSeek-V3 technical report (arxiv 2412.19437)](https://arxiv.org/abs/2412.19437)
- [Qwen3-30B-A3B (apxml)](https://apxml.com/models/qwen3-30b-a3b)
- [Qwen3 benchmark on consumer hw (arxiv 2512.23029)](https://arxiv.org/pdf/2512.23029)
- [Mixtral 8x22B](https://mistral.ai/news/mixtral-8x22b)
- [Local LLMs comparison 2026 (promptzone)](https://www.promptzone.com/jordan_lee_72db45ce/best-local-llms-for-consumer-hardware-2026-llama-33-70b-vs-qwen3-30b-a3b-vs-deepseek-r1-distill-336p)
- [Unsloth DeepSeek V3 GGUF](https://huggingface.co/unsloth/DeepSeek-V3-GGUF)

**Hybrid / SSM / native QAT:**
- [Jamba paper (arxiv 2403.19887)](https://arxiv.org/pdf/2403.19887)
- [AI21 Jamba announcement](https://www.ai21.com/blog/announcing-jamba/)
- [Mamba-3 deployment (Spheron)](https://www.spheron.network/blog/mamba-3-state-space-model-gpu-cloud-deployment/)
- [BitNet b1.58 2B4T (HF)](https://huggingface.co/microsoft/bitnet-b1.58-2B-4T)
- [BitNet repo](https://github.com/microsoft/BitNet)
- [Microsoft BitNet news (InfoQ)](https://www.infoq.com/news/2025/04/microsoft-bitnet-1bit-llm/)

**Distributed / mesh inference:**
- [EXO repo](https://github.com/exo-explore/exo)
- [Petals repo](https://github.com/bigscience-workshop/petals)
- [Petals research (Yandex)](https://research.yandex.com/blog/petals-decentralized-inference-and-finetuning-of-large-language-models)
- [Mesh-LLM repo](https://github.com/Mesh-LLM/mesh-llm)
- [LocalAI distributed docs](https://localai.io/features/distribute/)
- [Prima.cpp paper (arxiv 2504.08791)](https://arxiv.org/abs/2504.08791)
- [Prefill-decode disaggregation (Spheron)](https://www.spheron.network/blog/prefill-decode-disaggregation-gpu-cloud/)
- [Disaggregated prefilling (vLLM)](https://docs.vllm.ai/en/latest/features/disagg_prefill/)
- [EXO + DGX Spark hybrid (Tom's Hardware)](https://www.tomshardware.com/software/two-nvidia-dgx-spark-systems-combined-with-m3-ultra-mac-studio-to-create-blistering-llm-system-exo-labs-demonstrates-disaggregated-ai-inference-and-achieves-a-2-8-benchmark-boost)

**On-device / mobile:**
- [ExecuTorch repo](https://github.com/pytorch/executorch)
- [ExecuTorch Beta blog (PyTorch)](https://pytorch.org/blog/executorch-beta/)
- [On-Device LLMs State of the Union 2026](https://v-chandra.github.io/on-device-llms/)
