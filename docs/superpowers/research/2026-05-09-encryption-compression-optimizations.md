# Encryption + Compression Optimizations Across OCM's Layered Stack

**Date:** 2026-05-09
**Trigger:** User question — "what optimizations can be found through encryption and compression."
**Scope:** Identify OCM-specific opportunities beyond the standard practice (TLS + zstd everywhere). Map each to the layered architecture, identify the threat model or compression-ratio target, and either lock as a spec decision or flag as research-grade.

## The framing principle

Encryption and compression both shrink the cost of moving and storing data, but they answer different questions:

- **Compression** asks: *can we say the same thing in fewer bits?*
- **Encryption** asks: *can we say the same thing such that only authorized parties can read it?*

These compose ordered: **compress then encrypt**, never the reverse. Encrypted bytes are random by design, so post-encryption compression saves nothing. This is standard cryptographic wisdom but worth stating explicitly because the order is load-bearing for every layer.

OCM's architecture has six layers (per the [Effective-Context Triad](2026-05-09-effective-context-triad-expansion-stratification-lookup.md)). Every layer has both axes — we map them systematically below.

## Compression — five strategies already locked, three to add

### Already locked in v0.4 spec (named and unnamed)

| Compression strategy | Where in spec | Mechanism | Effective ratio |
|---|---|---|---|
| Weight quantization (Q4_K_M / AWQ-INT4) | row 6, 17, 18 | int4 instead of fp16 | **4×** weight memory + bandwidth |
| Aider-style repomap | row 24 | NetworkX PageRank + tree-sitter compress | **~70% token reduction** (claimed; needs sandbox confirmation) |
| Library-driven retrieval (Mem0 v3) | row 9 | retrieve 7K relevant tokens vs stuffing 100K context | **~14×** effective context ratio |
| Schema compression for MCP tools | row 21 | strip descriptions, shorten param names, hide optional params | **30-60%** per-request token reduction |
| RadixAttention prefix-cache deduplication | row 5 | shared system prompt computed once across N users | **~3-5×** aggregate vs naive serving |
| DSPy GEPA-compiled skills | row 23 | program artifact ≪ equivalent prompt+fewshots | **~10×** skill density (claimed by DSPy paper) |
| Hermes XML+JSON tool format | row 20 | denser format than verbose OpenAI JSON for small models | **+12-19pp tool-call accuracy** at slightly fewer tokens |

These compound. A request hitting the full stack of locked compression: Q4 weights (4×) × continuous batching (4× aggregate) × RadixAttention (~3×) × library-driven retrieval (~14× context) = **~670× effective compression** vs naive fp16 + stuff-everything-in-context baseline. (Research note `2026-05-08-per-node-efficiency.md` already calibrates this; numbers are ceiling not floor.)

### To add (this note locks them as decision rows)

#### 1. At-rest storage compression — zstd on palace + Mem0 stores

Markdown palace nodes are highly compressible (text + structured frontmatter). zstd level 19 hits ~3-5× compression on real markdown corpora. Mem0's SQLite store with sqlite-vec also compresses well — vector blobs are not particularly compressible (~1.2×) but the metadata + text columns compress 3-4×.

**Verdict: lock as v3.5+ Memory Palace implementation detail.**
- Local palace stores zstd-level-19-compressed at rest
- Mem0 SQLite uses zstd-compressed VFS layer (sqlite-zstd extension exists; well-tested)
- Decompression overhead is sub-millisecond on modern CPU; doesn't violate quick-look-up latency budget

Cost: ~2-5× CPU on writes (negligible — palace writes are user-driven, low-frequency). Saves ~70% local disk for typical knowledge stores. Worth it.

#### 2. Wire-level compression — zstd on iroh-blobs + libp2p transport

iroh-blobs is content-addressed and deduplicates by blob hash, which is a form of compression (a blob shared across N peers is stored once locally). Adding zstd on top gives additional compression for unique blobs. libp2p has experimental gzip support; zstd is more efficient.

**Verdict: lock as v2 mesh transport detail.**
- All mesh-transported markdown payloads compressed with zstd before signing+encrypting
- Inference RPC payloads (chat completion requests) compressed with brotli (better for HTTP)
- Effective: 60-80% bandwidth reduction on text-heavy mesh payloads

Cost: ~1-3% CPU on the sender, similar on receiver. Savings: 60-80% bandwidth. **Ratio of CPU cost to bandwidth saved is overwhelmingly favorable on residential internet.**

#### 3. Activation compression for sharded inference (v6+)

When OCM v6 ships sharded inference (Exo + Prima.cpp pattern), activations passed between pipeline-parallel nodes are by default fp16 (~2 bytes per activation). Quantizing to fp8 or even int8 cuts that in half or more.

This is **the single biggest unlock for residential-WAN sharded inference.** Per the per-node-efficiency research, the limiting factor for Petals-style sharded inference on residential bandwidth (1-10 Mbps upload) is the activation transfer rate. A fp16 → fp8 swap doubles the model size that's viable to shard.

**Verdict: lock as v6+ implementation detail; research the accuracy impact ahead of time.**
- Activations transferred in fp8 by default with fp16 fallback
- Optional int4 activation transfer for extreme bandwidth-constrained users (researched, not default)
- Bench framework: Sandbox H (TBD) measures sharded-inference accuracy delta vs activation precision

**Caveat:** activation quantization is *not* the same as weight quantization. The accuracy impact is more sensitive to outliers in attention scores. Production fp8 activations work in NVIDIA H100 inference but are less battle-tested at fp4 / int4. Treat as an opportunity to measure rather than commit blindly.

## Encryption — three threat models, three primitives

OCM's privacy zones from the v0.4 Memory Palace research note define the structural slots; this note specifies the cryptographic primitives that fill them.

### Zone A — Local-only Mem0 (threat: disk theft, backup leak)

**Primitive: SQLCipher with user-passphrase-derived key.**

- Mem0 stores in `~/.ocm/mem0.db` go through SQLCipher's transparent AES-256 encryption
- Key derived from user passphrase via Argon2id (memory-hard, modern KDF)
- Passphrase entered once at OCM startup; held in memory for session duration
- No network exposure; threat model is "physical disk access only"

**Cost:** SQLCipher adds ~5-15% query latency vs unencrypted SQLite. Mem0's retrieval budget is 300ms; encrypted variant is ~330-350ms. Acceptable.

**Verdict: lock as v1 implementation detail.**

### Zone B — Personal palace (threat: backup/cloud-sync leak)

**Primitive: age (Filippo Valsorda's modern alternative to GPG) for at-rest, Ed25519 for signing.**

- User has a long-lived OCM identity keypair (Ed25519) generated at first run, stored encrypted with passphrase in OS-native secrets store (Keychain on macOS, DPAPI on Windows, libsecret on Linux)
- Personal palace nodes can be optionally encrypted-at-rest with `age` using a key derived from the same identity
- Every commit to the personal palace is signed with the Ed25519 key (the same key used for mesh signatures in Zone C)
- Recovery: passphrase + the encrypted keypair are sufficient to reconstruct identity on a new device

**Why age over GPG:** GPG's PGP web-of-trust is overcomplicated for our model. age is intentionally minimal — encrypt for one or more recipients, decrypt with one private key. ~5K LOC vs GPG's ~250K, vastly easier to audit. Already used in production by ssh-config encryption tools.

**Cost:** age encryption is ~50 MB/s on modern CPU; palace nodes are KB-MB, so encryption overhead is sub-millisecond. Negligible.

**Verdict: lock as v3.5+ Memory Palace implementation detail.**

### Zone C — Mesh-published palace nodes (threat: untrusted peer + mesh-wide inspection)

**Primitive: Ed25519 signatures (always); age recipient encryption (when private group sharing).**

Two sub-cases:

**(a) Public mesh nodes** — `mesh: public` frontmatter, replicated by OCM mesh, intended to be world-readable:
- Cleartext payload (anyone can read, that's the point)
- Ed25519 signature over the SHA-256 of the canonical-form payload (signature included in commit metadata)
- Subscribers verify signatures on every retrieval before trusting content
- Tampering detection: 100% (signature fails); unauthorized publishing prevention: 100% (no valid keypair)

**(b) Private group shares** — `mesh: group@<group-id>` frontmatter:
- Payload encrypted with `age` to N recipient public keys (the group members' OCM identity public keys)
- Encrypted payload signed by author with their Ed25519 key
- Mesh peers can replicate the encrypted blob but not read it
- Group recipients decrypt locally with their private key

**Cost:** Ed25519 signing/verification is ~50-100µs per operation. age encryption is ~50 MB/s. For typical palace nodes (KB-MB range), the cryptographic overhead is in the low-millisecond range. Doesn't violate any latency budget.

**Verdict: lock as v3.5+ Memory Palace implementation detail.**

### Cross-cutting: Mesh transport TLS

iroh's QUIC transport already provides TLS 1.3 by default — every connection is encrypted in transit between peers without needing to add a separate layer. libp2p's secio / noise transport similarly. **No additional work needed at the transport layer.** The Zone-A/B/C cryptography is end-to-end encryption layered on top of transport encryption — defense in depth.

## Sharded inference encryption — confidential computing (v6+ research, deferred)

A speculative angle: when v6+ borrows compute from a contributor for sharded inference, the contributor sees the activations in plaintext (they have to, to compute on them). For privacy-sensitive workloads, this is a leak.

**Two existing mitigations:**
- **Trusted Execution Environments (TEEs)** — Intel SGX, AMD SEV-SNP, NVIDIA H100 Confidential Computing. The model + inputs are processed inside an enclave; the host machine's operator cannot see plaintext. Requires hardware support; Mac M-series doesn't have it (yet); RTX 4090 doesn't have it (only H100+).
- **Fully Homomorphic Encryption (FHE)** — Compute on encrypted data without decrypting. Mathematically real, practically ~10000× slower than plaintext. Not viable for inference on consumer hardware in 2026.

**Verdict: research-grade for v6+, NOT a commit.**

The honest current state: OCM mesh inference is not privacy-preserving against a malicious peer who controls the borrowed-machine. Document this clearly in user-facing docs. For privacy-sensitive workloads, users should run locally only. v6 sharded inference is for *latency-tolerant + non-sensitive* workloads.

This is a real architectural limit. We name it explicitly rather than pretending FHE is just around the corner.

## Where compression and encryption *interact* — three specific gotchas

### 1. Compress-then-encrypt order is mandatory

Encrypted bytes are random by design. zstd-after-encrypt achieves no compression. Every place in OCM that does both must compress *first*. This is enforced via the canonical pipeline:

```
plain payload
  → canonical-form serialize
  → zstd compress (or brotli for HTTP)
  → age encrypt (Zone B/C)
  → Ed25519 sign over the encrypted-compressed bytes
  → transport
```

### 2. Length-leak attacks via compression

Even encrypted, a compressed-then-encrypted payload's *length* leaks information about content (CRIME, BREACH attacks). For palace nodes published to the mesh, this is mostly fine (the content is public anyway, signed not encrypted) but for Zone C *private* group shares, an attacker can sometimes infer content from compression-ratio patterns.

**Mitigation:** for Zone C private group shares only, pad encrypted payloads to power-of-2 length buckets (128B, 256B, 512B, 1KB, 2KB, ... 64KB). Costs ~30% bandwidth on average; eliminates length-leak signal. Worth it.

### 3. Compressed-skill artifact verification

DSPy GEPA artifacts (locked v2+ as skill federation primitive) need cryptographic provenance. Two options:

**(a) Sign the compressed artifact directly.** Signature verification reads the compressed bytes, no decompression needed for trust. This is the simple choice.

**(b) Sign the canonical decompressed artifact.** More flexible (the compression algorithm can change without invalidating signatures) but requires decompression-before-verify, which is annoying.

**Verdict: option (a). Sign compressed artifact bytes; if compression algorithm changes, re-sign.** Spec already locks Ed25519 signatures on skill artifacts in row 23; this clarifies signing is over the wire-format bytes.

## Recommended bench-framework instrumentation

Three new sandboxes to validate the claims in this note. They get added to the existing bench framework when v3.5 / v6 work begins.

### Sandbox G — Wire compression bandwidth savings

**Path:** `bench/isolation/transport/zstd-mesh-payload-compression/`

```json
{
  "hypothesis_id": "zstd-mesh-payload-compression",
  "claim": "zstd level 6 compression on mesh-transported palace markdown payloads achieves >=60% bandwidth reduction on real palace corpora at <=5ms p50 compression overhead per KB",
  "metric": "compression_ratio_pct",
  "thresholds": {"confirm_at_least": 60.0, "refute_below": 40.0},
  "secondary_metric": "compression_latency_ms_per_kb_p50",
  "secondary_thresholds": {"confirm_at_most": 5.0, "refute_above": 15.0},
  "workload": "palace-markdown-corpus-1000-nodes.jsonl",
  "timeout_seconds": 600
}
```

### Sandbox H — Activation-transfer fp8 vs fp16 quality

**Path:** `bench/combination/sharded-inference-fp8-activations/`

```json
{
  "hypothesis_id": "sharded-inference-fp8-activations",
  "claim": "Sharded inference with fp8 activation transfer between mesh nodes maintains >=98% of fp16 accuracy on a held-out 100-question agent-task benchmark, while halving inter-node bandwidth",
  "metric": "accuracy_pct_relative_to_fp16",
  "thresholds": {"confirm_at_least": 98.0, "refute_below": 92.0},
  "secondary_metric": "bandwidth_reduction_pct",
  "secondary_thresholds": {"confirm_at_least": 45.0, "refute_below": 25.0},
  "workload": "agent-task-benchmark-100q.jsonl",
  "timeout_seconds": 14400
}
```

### Sandbox I — Encrypted-Mem0 query latency overhead

**Path:** `bench/isolation/encryption/sqlcipher-mem0-overhead/`

```json
{
  "hypothesis_id": "sqlcipher-mem0-overhead",
  "claim": "SQLCipher-encrypted Mem0 retrieval adds <=15% latency vs plaintext SQLite on a 100K-conversation Mem0 corpus, keeping p50 query latency <=350ms",
  "metric": "latency_pct_increase_vs_plaintext",
  "thresholds": {"confirm_at_most": 15.0, "refute_above": 40.0},
  "secondary_metric": "absolute_p50_ms",
  "secondary_thresholds": {"confirm_at_most": 350.0, "refute_above": 600.0},
  "workload": "mem0-retrieval-100k-conversations.jsonl",
  "timeout_seconds": 1800
}
```

## Decision summary — what to lock vs research vs defer

| Optimization | Verdict | Where in spec |
|---|---|---|
| zstd at-rest (palace + Mem0) | **Lock — v3.5+ implementation** | Decision row 28 below |
| zstd/brotli wire compression (mesh payloads) | **Lock — v2 implementation** | Decision row 28 below |
| fp8 activation transfer (sharded inference) | **Lock with sandbox-gate — v6+** | Decision row 29 below; gates on Sandbox H confirming |
| SQLCipher Mem0 at-rest encryption | **Lock — v1+ implementation** | Decision row 30 below |
| age encryption for personal palace at-rest | **Lock — v3.5+ implementation** | Decision row 30 below |
| Ed25519 signatures on Zone C nodes | **Already implicit in row 26; reaffirmed** | (no new row) |
| age recipient encryption for private group shares | **Lock — v3.5+ implementation** | Decision row 30 below |
| Length-leak padding for Zone C private | **Lock — v3.5+ implementation detail** | Mentioned in research note; no separate row |
| TLS at transport layer | **Already provided by iroh QUIC** | (no new row) |
| TEE-based confidential inference | **Research-grade; defer to v6+ research, NOT lock** | Documented as honest limit |
| FHE-based privacy-preserving inference | **Defer indefinitely; ~10000× slower than plaintext** | Documented as honest limit |

## Bottom line for OCM

Encryption and compression aren't two separate optimization tracks; they're a single coordinated layer that touches every component of the stack. The user's question prompts us to:

1. **Name** the compression strategies already locked but not previously framed as compression (Mem0 retrieval, repomap, schema compression, RadixAttention, DSPy skills, quantization)
2. **Lock** the obvious-good-engineering compression additions (zstd at-rest, wire compression, fp8 activations gated by sandbox)
3. **Lock** the obvious-good-engineering encryption additions per privacy zone (SQLCipher Zone A, age Zone B/C, Ed25519 signatures already implicit)
4. **Honest about limits** — sharded inference is not privacy-preserving against a malicious peer in 2026; TEE is hardware-gated; FHE is decade-out

The non-obvious cumulative point: **OCM's compression strategies compound across layers**. A query that hits the full stack uses ~670× less compute and ~75% less bandwidth than naive fp16 stuff-everything-in-context. The mesh works on residential internet *because* of this stacking. Encryption + at-rest compression layered on top adds <10% overhead while delivering meaningful privacy + cost savings — overwhelmingly favorable cost/benefit.

Future engineering discipline: any new feature that *fails* to compose with the existing compression pipeline is suspect. A v3.5 palace-search pipeline that decompresses-and-recompresses three times is broken architecture. The pipeline contract is "compress once, decrypt once, deliver to model" — anything else is a violation.

This research note becomes the reference for that contract.
