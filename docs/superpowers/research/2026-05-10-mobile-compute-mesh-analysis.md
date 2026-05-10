# Mobile Compute on the OCM Mesh — Research Note

> **Date:** 2026-05-10
> **Author:** Brand + analysis synthesis
> **Status:** Reference doc behind spec v0.7 row 33 (Mobile compute policy)
> **Companion:** `2026-05-09-remote-node-deployment.md`, `2026-05-09-encryption-compression-optimizations.md`

## Question

Spec v0.1-v0.6 said nothing about mobile devices. Phones and tablets in 2026 have meaningful inference capability — the iPhone 17 Pro's NPU runs ~45 TOPS, M5 iPad Pro is laptop-class. Should they participate in the OCM mesh? If so, in what role? With what defaults?

## TL;DR (the locked v0.7 policy)

Two participation modes, staged across v1.5 / v2.5 / v3.5:

- **Consumer** (default-on, ships v1.5) — phone/tablet uses mesh compute via the existing `/v1/*` HTTP API. Native client is a Capacitor or Tauri 2 mobile shell wrapping the existing SvelteKit frontend.
- **Opportunistic contributor** (default-OFF) — phone/tablet donates compute back, gated on (charging AND WiFi AND foreground) OR an explicit user "donate now" press. Tablet first (v2.5), phones (v3.5) with conservative defaults.

Three explicit non-goals locked in row 33: never full off-foreground / off-charger phone participation; cellular-data contributions remain off by default; no privileged Apple-Intelligence / system-NPU API path in v1.x.

## Why these specific gates

### Battery economics

A representative iPhone 17 Pro running an 8B Q4 model via MLC-LLM at sustained 12-15 tok/s draws ~5-7W under load. A 4400 mAh battery (~16.7 Wh) gives 2.5-3 hours of continuous inference *if* nothing else is happening — which never happens on a phone. Real-world: 30-60 minutes before thermal throttling kicks in and the user notices battery drain. That's the constraint.

The "charging AND WiFi AND foreground" gate is the smallest set that produces predictable battery experience:

- **Charging** — battery drain becomes the wall's problem, not the user's
- **WiFi** — no metered-data surprise; cellular contributions are explicit opt-in only
- **Foreground** — iOS aggressive background throttling makes off-foreground compute economically nil; cleaner to just say "active app only"

Phones in pockets between charges = consumers, not contributors. That's honest.

### iOS App Store policy realism

Apple's review team is increasingly cautious about apps that "function as a marketplace or contribute computation to a network." Concrete precedents from 2024-2026:

- BOINC iOS — BOINC's volunteer-compute app has had on-and-off App Store availability; current state is sideload-friendly with TestFlight options
- Folding@home iOS — never made it to the App Store; community sideload only
- Petals "test" iOS clients — TestFlight only, never approved for App Store
- Apple Intelligence framework — system-level NPU access is reserved; third parties access via the `Foundation Models` API which is read-only-from-Apple's-perspective

Implication: v1.5 ships via TestFlight (iOS) + F-Droid (Android) + APK sideload. App Store distribution becomes feasible only after v4 codesigning + Apple Developer Program membership + a clean App Review story focused on "personal-AI client" framing. Don't rely on App Store distribution for the v1.5 launch.

### Tablet-first contributor staging

iPad M-series ≠ phone. Specifics:

- M4 iPad Pro: 16 GB RAM unified memory pool, sustained 10W TDP under load, no thermal throttling for 30+ min
- Battery: 36-40 Wh (vs 16-18 Wh on a flagship phone). At 7W sustained that's 4-5 hours of inference vs 60 min on a phone
- Use pattern: tablets are more often docked/charging at home (kitchen, desk, kids' setup) than phones
- Performance: 13B Q4 models at 15-25 tok/s with MLC-LLM Metal backend — comparable to a 2018 Mac mini

Phones become contributors at a measurable disadvantage; iPad gets there cleanly. Staging tablet first (v2.5) before phone (v3.5) lets the tablet path prove the contributor mode end-to-end with realistic battery economics, then phones inherit the same plumbing with conservative defaults.

## Tooling decisions (concrete picks)

| Layer | Pick | Reason |
|---|---|---|
| Inference engine | **MLC-LLM** (cross-platform via Vulkan/Metal/OpenCL) | Single codebase across iOS / Android / iPadOS. llama.cpp Metal works on iOS but App Store-compatible builds are awkward. MediaPipe LLM is Google-only. MLC-LLM picks up the cross-platform mantle. |
| Mesh transport | **iroh's Swift + Kotlin (uniffi-generated) bindings** | Iroh has first-party uniffi support; mesh participation is real, not a port. libp2p-mobile remains escape hatch per spec row 8. |
| App shell | **Capacitor or Tauri 2 mobile** wrapping SvelteKit | Reuses the existing frontend codebase 1:1. Tauri 2 mobile is closest to the desktop story (Rust core + web UI) but Capacitor is more battle-tested as of 2026. Final pick deferred to v1.5 implementation; both are listed in row 33 |
| Background execution (iOS) | **BGTaskScheduler with PROCESSING task identifier** | Apple's blessed background path for "useful work while plugged in." Used by photo libraries + sync clients. Gives a deterministic 30s-2min window when the app is in the background but the device is charging. |
| Background execution (Android) | **Foreground Service with `dataSync` type + WorkManager** | Foreground service shows a persistent notification; user always knows compute is happening. WorkManager schedules windows that respect Doze + App Standby. |
| Mobile keystore | **iOS Keychain Services + Android Keystore (hardware-backed)** | Per spec row 29 mapping. Both expose Secure Enclave / StrongBox where available — actually a security UPGRADE over typical Linux libsecret on desktop |

## Threat model differences vs desktop

Mobile shifts three threat-model assumptions:

1. **Physical theft is a higher base rate.** Phones get lost/stolen at orders of magnitude higher rates than laptops. Implication: Zone A encryption (already on per spec row 29) becomes load-bearing, not defense-in-depth. Same shift as remote-VM deployment per spec row 31.
2. **OS-mediated app sandboxing is stricter.** iOS App Sandbox + Android UID isolation prevent many cross-app attack patterns that desktop libraries assume away. Net: smaller effective attack surface for a given exploit class.
3. **Secure Enclave / StrongBox actually exist.** Hardware-backed key storage with attestation is the default on every shipped device since 2017 (iPhone 5s+) / 2019 (Android 10+). On Linux desktop, hardware-backed key storage is rare. Net: mobile encryption story is structurally STRONGER than Linux desktop story.

Honest limit: a sufficiently-resourced adversary can still extract keys from a stolen device, especially older hardware. The threat model is "lost phone, opportunistic finder" — not "nation-state forensics lab."

## Distribution paths (sanctioned + unsanctioned)

| Distribution | When | What |
|---|---|---|
| TestFlight (iOS) | v1.5 onward | Up to 10K external testers per app. Current standard for OSS iOS apps avoiding App Review |
| F-Droid (Android) | v1.5 onward | OSS-friendly app store; reproducible builds preferred. Aligns with OCM's Apache-2.0 license |
| APK sideload (Android) | v1.5 onward | Direct download from `releases/v1.5.x.apk`. Not for everyone but maintains optionality |
| App Store (iOS) | v4+ (after codesigning + review) | Requires Apple Developer Program + clean review story. "Personal AI client" framing is more likely to pass than "decentralized compute marketplace" |
| Google Play | v4+ | Less restrictive than iOS but Play Protect flags new apps; meaningful traction gates approval. Consider v4+ when there's a track record |

## Per-device contribution math (honest)

The "value of mobile contribution to the mesh" is aggregate-at-scale, not per-device. Realistic:

- Active phone contributor (charging + WiFi + foreground), opt-in: ~30 min/day average if user actually uses the toggle
- Per-device output at 12 tok/s: ~22K tokens/day
- 10K active phone contributors: ~220M tokens/day aggregate ≈ ~2.2K user-equivalent days of inference
- 100 active iPad contributors (charging at home): each 4hr × 25 tok/s = ~360K tokens/day each, ~36M tokens/day aggregate from just 100 tablets

The economic case isn't "every phone contributes" — it's "tablets carry the contributor load; phones are mostly consumers; the consumer side drives adoption; the contributor side scales with iPad penetration in the contributor cohort."

## Implementation roadmap (binding)

| Version | Effort estimate | Deliverable |
|---|---|---|
| **v1.5** | ~4-6 weeks (one engineer) | iOS + Android consumer client. Capacitor/Tauri 2 shell + existing SvelteKit. Connects to a desktop OCM over LAN via /v1/* HTTP. TestFlight + F-Droid distribution. No compute contribution. |
| **v2** | per existing roadmap | Real iroh / libp2p mesh transport with mobile bindings activated |
| **v2.5** | ~6-10 weeks | iPad opportunistic contributor mode. MLC-LLM + iroh Swift bindings. Charging + WiFi + foreground gates. "Donate compute now" UI toggle. Battery + thermal observability dashboard for the user. |
| **v3.5** | ~4-6 weeks (mostly UX polish on the v2.5 plumbing) | Phone opportunistic contributor mode. Same gates, more conservative defaults (e.g. minimum 80% battery, max 30 min sessions). Cellular contribution is explicit opt-in with metered-data warning. |
| **v4** | per existing roadmap | Codesigning + auto-update; mobile App Store distribution path activates |

## Disconfirmation triggers

The locked policy gets revisited if any of the following land:

1. **Apple opens up Foundation Models for delegation** — system-level NPU access for third parties would change the per-device math substantially
2. **Battery technology jumps** — silicon-anode batteries hitting 50% energy density gain in flagship phones would shift the "phones are mostly consumers" framing
3. **iOS App Store relaxes "marketplace" rules** — would unlock direct App Store distribution earlier than v4
4. **Cellular 5G+ unmetered plans become standard** — would shift the "WiFi-only contribution" default. As of 2026 this hasn't happened broadly
5. **Sandbox F (Memory Palace effective-corpus) refutes the load-bearing claim** — would change the value of mobile contributors at all (smaller corpus → less benefit from added compute)

If a disconfirmation lands, row 33 gets re-evaluated and either softens or tightens the gates accordingly.

## Bench sandbox slot (proposed v0.7.1)

A future INACTIVE sandbox at `bench/isolation/mobile/consumer-client-latency` would test:

> "iPad consumer client connecting to a desktop OCM over LAN exhibits ≤100ms median first-token latency on a 50-prompt suite, comparable to a desktop browser client on the same network."

This validates v1.5's value proposition (consumer mobile is responsive, not laggy) without requiring contributor-mode plumbing. Status: stays INACTIVE until v1.5 lands.

## Honest non-recommendations

- Do NOT promise "phones power the mesh" in marketing copy. Per-phone contribution is small; aggregate matters but the per-device story is misleading.
- Do NOT pursue iOS App Store distribution before v4. Review-team pushback on "compute marketplace" framing is high-probability; TestFlight + F-Droid + sideload are perfectly adequate for v1.5-v3.5 contributor cohort.
- Do NOT bundle Apple Intelligence integration in v1.x. The Foundation Models API is read-only-from-Apple's-perspective and ties OCM to Apple's roadmap in a way that breaks cross-platform parity.
- Do NOT over-architect for cellular contributions. Default-off + metered-data warning + explicit opt-in is sufficient. Don't build cellular-bandwidth-budget UX until there's evidence users want it.

## Related

- Spec row 6 — Apple Silicon scope extended to iPad M-series
- Spec row 8 — iroh Swift + Kotlin bindings for mobile transport
- Spec row 13 — platform list expansion with consumer/contributor split
- Spec row 29 — mobile keystore mapping (iOS Keychain + Android Keystore)
- Spec row 31 — VM/cloud deployment policy (the closest precedent for non-desktop hardware participation)
- `docs/superpowers/research/2026-05-09-encryption-compression-optimizations.md` — encryption pipeline that mobile keystores plug into
