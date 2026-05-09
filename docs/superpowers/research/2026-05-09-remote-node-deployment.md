# Remote-Node Deployment Strategy

> **Date:** 2026-05-09
> **Author:** Brand + research synthesis
> **Status:** v1 reference — covers VM/cloud deployment policy locked as spec row 31
> **Companion:** `2026-05-09-decentralized-memory-palace-pattern.md`, `2026-05-09-encryption-compression-optimizations.md`

## Question

OCM is framed as "free idle compute on user-owned hardware." When does a remote VM (Hetzner, Fly.io, DigitalOcean, AWS) fit into that framing without breaking it? What changes about the architecture, security, and UX when an OCM daemon runs on rented infrastructure rather than the user's physical machine?

## Three distinct uses of remote VMs

The literal "OCM running on a VPS" question hides three very different use cases. They have different threat models, different cost shapes, and different roles in the v1→v6 roadmap.

### Use 1: Bench / test fleet (now)

Running multiple `ocm-daemon` instances on cloud VMs to validate behavior under realistic WAN conditions. This is what the OCM bench framework's `mesh-transport/wan-relay-node` sandbox slot exists for. Cost is amortized across all contributors; nodes are ephemeral; nothing user-private touches them.

- **Cost:** ~$5/mo for a Hetzner CX21 or DigitalOcean droplet running an idle daemon
- **Privacy concern:** none — bench fleet runs synthetic workloads, no user memory
- **Roadmap fit:** active now, exercised every time mesh sandboxes run

### Use 2: Seed / relay nodes (Phase 7+)

Always-on volunteer-run nodes whose entire job is helping peers behind NAT discover each other and bootstrap the iroh DHT. They do **not** run inference. They are the peer-to-peer-network equivalent of IPFS bootstrap nodes or libp2p relays.

- **Cost:** $4-10/mo per node; OCM might run 3-5 (one per region) for ~$30/mo total
- **Privacy concern:** mostly contained — relay nodes see encrypted QUIC traffic but not plaintext
- **Roadmap fit:** Phase 7+ "Public Bootnet" milestone (v4 in the roadmap)
- **Funding model:** community / sponsor (Hetzner OSS credits, Cloudflare zero-trust tier, Fly.io OSS plan)

### Use 3: Inference-as-a-service on a remote VM (out of scope)

A user runs OCM on a VPS instead of their own laptop because their laptop can't host the model. Conceptually possible — `ocm-daemon` doesn't care if it's on bare metal or a VM. But this **breaks the local-first framing** and turns OCM into "Llama on a VPS," which is a different product (Replicate, RunPod, Together AI all already exist).

- **Cost:** $50-300/mo for a useful GPU VM
- **Privacy concern:** Zone A (user's "local" Mem0) now sits on third-party infrastructure with all the implications that brings — disk encryption matters more, key custody matters more, threat model is no longer "single-user laptop"
- **Roadmap fit:** **explicitly out of scope for v1**. Document the caveats so users who do this anyway understand the tradeoff. Don't optimize for it, don't bundle it.

## What the spec already locks (rows 26-30) and where remote VMs fit

| Spec lock | How it constrains remote-VM deployment |
|---|---|
| Row 8 — iroh + libp2p escape hatch | Mesh transport already handles WAN. Adding remote nodes doesn't require new transport work. |
| Row 9 — Mem0 v3 + OpenMemory MCP local mode | "Local mode" presupposes the user owns the machine. Remote VM = nominal "local" but trust boundary is now the cloud provider. Spec row 31 (this doc's deliverable) names this. |
| Row 26 — Memory Palace privacy zones A/B/C | Zone A's threat model degrades on a remote VM; Zone B (personal palace, signed) is fine; Zone C (mesh-published) is unaffected. |
| Row 27 — Effective-Context Triad | Quick-Look-Up budgets assume LAN-class latency to memory layers. Remote VMs would force re-tuning — at-rest disk on the same VM is fine; cross-VM memory access is not. |
| Row 28 — Compression pipeline | Wire compression (zstd-6 / brotli) becomes more valuable on WAN. Same algorithm, higher leverage. |
| Row 29 — Encryption mapped to zones | SQLCipher on Zone A is necessary, not optional, on a remote VM. Argon2id-from-passphrase is fine; OS-secrets-store key custody isn't (no Keychain on a Linux VM). Document the keychain-substitute path. |
| Row 30 — Compress-then-encrypt | Unchanged. |

## Concrete v1 policy (spec row 31)

The proposed locked decision for the spec:

> **OCM v1 daemon runs on user-owned hardware by default.** Remote VM deployments are supported in two specific shapes — bench/test fleets (any time) and Phase 7+ relay nodes (community-run, no user memory) — and explicitly NOT supported as a sanctioned "OCM on a VPS for inference" path in v1. The v1 documentation will name this distinction so users who deploy on a remote VM anyway understand the threat model has shifted: Zone A encryption stops being a defense-in-depth and becomes load-bearing; key custody requires a Keychain substitute (e.g., `pass` + GPG, age + a passphrase, or a hardware token); and "local-first" means "this user's compute" not "this user's physical machine."

## Tool recommendations for the bench/test fleet (use 1)

Researched 2026-05-09. Cost figures are listed-price, USD, monthly:

| Tool | Best for | Cost (5-node fleet, idle) | Notes |
|---|---|---|---|
| **Multipass** | Local single-host fleet | $0 (uses host's CPU/RAM) | ✅ Sandbox `multipass-fleet` chosen for this |
| **Hetzner Cloud CX21** | EU-hosted WAN fleet | $20 (5 × $4) | Cheapest credible WAN; sponsors OSS |
| **Hetzner CCX13 (dedicated CPU)** | Reproducible perf benchmarks | $65 (5 × $13) | Dedicated cores eliminate noisy-neighbor variance |
| **DigitalOcean basic droplet** | US-hosted WAN fleet | $30 (5 × $6) | DO Community Sponsorship may cover for OCM eventually |
| **Fly.io shared-cpu-1x** | Globally-distributed fleet | $10 (5 × $2 if you stay in OSS plan) | Great for "5 nodes in 5 regions" topology tests |
| **Linode Nanode** | US-hosted WAN fleet | $25 (5 × $5) | Akamai-owned, OSS credits available |
| **AWS t4g.nano (Graviton)** | ARM coverage | $15 (5 × $3) | Good for ARM peer testing; spot pricing 70% off |

For Phase 7+ relay nodes (use 2), the same shortlist applies; recommend starting with one Hetzner CX21 in Falkenstein DE + one DO droplet in NYC + one Fly machine in IAD or SFO. Three nodes, three providers, three regions — costs ~$15/mo total, easily covered by sponsor credits.

## Multi-OS coverage via VMs

Local VMs solve a real OCM contributor problem: testing the daemon binary on Linux/macOS/Windows without owning all three. Documented patterns:

| Host OS | VM tool for guest = Linux | VM tool for guest = Windows | VM tool for guest = macOS |
|---|---|---|---|
| Linux | Multipass / KVM-libvirt | virt-manager + Win11 ISO | Not legally permitted |
| macOS | Multipass / Lima / OrbStack | UTM (QEMU/x64) — slow | UTM (Apple Silicon native) |
| Windows | WSL2 / Multipass / Hyper-V | Hyper-V native | Not legally permitted |

The `bench/isolation/mesh-transport/multipass-fleet` sandbox is Linux-guest-only by design (the daemon is the same binary on all platforms; cross-OS testing is the cross-OS-binary sandbox's job, not this one's). For cross-OS validation, use the existing `cross-platform-build` CI workflow which already tests ubuntu/macos/windows.

## Sybil-resistance implications (Phase 5+, but worth noting now)

The moment OCM runs on cheap rented compute, Sybil resistance becomes a real concern. A $4/mo droplet can host an OCM peer; an attacker spinning up 100 of those creates 100 nominal "peers" for ~$400/mo. Implications:

1. **Skill federation (DSPy GEPA artifacts) is robust to this.** Each artifact is signed; trust is bound to the signing key, not to the number of nodes serving it.
2. **Inference compute sharing (v6+) is NOT robust.** Byzantine peers can return wrong answers, lie about progress, drop work. Anti-Sybil work in v5 must precede v6 inference sharing on any meaningful scale.
3. **Memory Palace federation (row 26)** is in between. Signatures protect authenticity; what they don't protect is "my published palace becomes a flood-fill spam vector once 100 cheap nodes start subscribing and re-publishing." Subscription rate-limiting + reputation scoring belong in Phase 5+ alongside Sybil work.

This isn't a v1 problem because v1 is single-node by design. It IS a Phase 5+ problem the moment we encourage remote VMs.

## Recommended next moves

1. **Now (in this PR):**
   - Land spec row 31 (locks the policy above)
   - Land the `multipass-fleet` sandbox stub (committed early so the slot exists when Phase 7 mesh transport lands)
   - This research doc serves as the canonical reference

2. **Phase 7 (when mesh transport lands):**
   - Author the `multipass-fleet` harness wrapper (Python script in `bench/harness/`)
   - Add `wan-relay-node` sandbox using Hetzner OSS credits
   - Document key-custody substitute for Linux VM Zone A encryption (probably `age + passphrase` since `pass`+GPG has high friction)

3. **Phase 5+ (Sybil-resistance milestone):**
   - Reputation scoring spec
   - Subscription rate limits on Memory Palace
   - Pre-flight check: refuse to expand to v6 inference sharing until Sybil resistance ships

## Honest non-recommendations

- **Do not optimize OCM for "VPS as primary host."** Users will do it; don't bundle it as a supported path. Doing so blurs the "your compute, your memory" pitch and pulls UX work toward a use case that's better-served by existing GPU-VPS providers.
- **Do not run a public OCM bootnet without Sybil resistance.** A relay-only bootnet is fine, but the moment those nodes start participating in inference sharing or memory palace gossiping, we need v5's anti-abuse infrastructure or we ship a spam target.
- **Do not promise privacy guarantees you can't keep on a remote VM.** The honesty here is load-bearing for trust — "Zone A is local-first by design" stops being true on a VPS, and the spec / docs must say so.
