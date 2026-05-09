# Sandbox: multipass-fleet

**Hypothesis:** A 5-node OCM daemon fleet running on Multipass VMs on a single host discovers all peers within 30s and routes a 2-hop chat request with median latency under 500ms.

**Status:** **INACTIVE** — blocks on Phase 7+ mesh transport (libp2p/iroh) which is not yet implemented. The sandbox shape is committed early so the bench harness has a slot to fill once Phase 7 lands; until then it dry-runs only.

## What this measures (once active)

- **Discovery latency:** seconds from last-node startup until every node has a peer entry for every other node (5 nodes × 4 peers = 20 directed edges)
- **2-hop chat latency:** end-to-end seconds for `client → peer A → peer B → inference → response` across 20 trials. Peers A and B are randomly chosen from the fleet for each trial.
- **Discovery success rate:** fraction of trials where all 5 nodes converge to the full peer table inside the timeout

## What this does NOT measure

- WAN behavior (single-host VM fleet has no real NAT). For WAN testing see the `mesh-transport/wan-relay-node` sandbox (Phase 7+).
- Inference correctness — the chat hop returns a fixed canned reply; this is purely a transport/discovery test.
- Adversarial / Sybil resistance — single-tenant fleet, all nodes trusted. Sybil testing is a separate sandbox slated for v5.
- Bandwidth saturation — 2 vCPU / 2 GB VMs on a single host hit CPU limits long before they hit the bridge bandwidth ceiling.

## How to interpret (once active)

| Verdict | What it means |
|---|---|
| CONFIRMED | Mesh transport (Phase 7+) is correctly tuned for residential / single-host topology — proceed to WAN sandbox |
| REFUTED on discovery | Audit bootstrap configuration (mDNS / DHT bootnodes / iroh relay list) before expanding fleet |
| REFUTED on latency | Audit per-hop overhead — TCP stack, encryption handshake reuse, queue depth. Compare against the in-process baseline anchor |
| INCONCLUSIVE | Variance too high; expand from 5 to 10 nodes and rerun |

## Why a VM fleet (not just `cargo test`)

Mocking peers in unit tests doesn't catch:
- Real socket / port binding behavior
- OS-level NAT / loopback bridge quirks
- Per-process resource limits (file descriptors, port ephemeral ranges)
- iroh / libp2p QUIC handshake timings under realistic kernel scheduling

A VM fleet on a single host gives the closest reproducible proxy to "5 separate residential routers" without needing 5 physical machines.

## Tooling: Multipass

[Multipass](https://multipass.run) is Canonical's lightweight VM tool. Cross-platform (Linux/macOS/Windows), free, scriptable, ~100MB overhead per VM.

Provisioning sketch (planned harness, not yet implemented):

```bash
for i in $(seq 1 5); do
  multipass launch --name ocm-node-$i --cpus 2 --memory 2G --disk 5G 24.04
  multipass exec ocm-node-$i -- /bin/sh -c "curl -L https://example/ocm-daemon | sh"
done
```

The harness wrapper (`bench/harness/multipass_fleet.py`, planned) will:
1. Provision N VMs in parallel (defaults to 5)
2. Install the `ocm-daemon` binary on each (mounting from the host or pulling a release artifact)
3. Configure each daemon with the others as bootstrap peers
4. Start the fleet, capture timestamps, run discovery probe + 2-hop chat probe
5. Tear down deterministically

## Alternative tools considered

| Tool | Verdict |
|---|---|
| **Multipass** | ✅ chosen — cross-platform, free, scriptable, lightweight |
| Lima | Mac/Linux only — fine for dev but no Windows story |
| OrbStack | Mac-only + paid; faster than Multipass on M-series but excludes Windows contributors |
| firecracker | Linux-only + microVM; great for ephemeral CI fleets but the dev-experience cost is high for solo OSS |
| Docker Compose (containers, not VMs) | Doesn't exercise OS-level NAT / port binding — defeats the point of this sandbox |

If a contributor's environment can't run Multipass, this sandbox falls back to dry-run only on their machine; CI runs the real path on a single Ubuntu host.

## Hardware classes verified for this sandbox (once active)

- `linux-vm-host-8core-32gb` — primary target, fleet of 5 fits comfortably
- `mac-vm-host-m4-pro-24gb` — secondary target via Multipass on Apple Silicon
- `windows-vm-host-16core-32gb` — tertiary target via Multipass for Windows
- `cpu-only-laptop-8gb` — likely refutes or runs out of memory; document as expected fail mode

## Source for the claim

Internal hypothesis derived from:
- iroh QUIC residential success rate (~90% vendor-reported, ~80%+ independent estimates) — single-host fleet has no real NAT and should approach 100%
- libp2p mDNS discovery on LAN typically converges in <10s at fleet sizes ≤10
- 2-hop in-process routing latency on modern x86 is sub-millisecond; the per-hop QUIC encryption + scheduler overhead should keep median end-to-end under the 500ms target
