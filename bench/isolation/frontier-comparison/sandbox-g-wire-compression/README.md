# Sandbox G: Wire Compression Bandwidth

**Hypothesis:** zstd-6 on mesh payloads cuts bandwidth 60-80% with ≤2ms compress+decompress overhead.

**Status:** INACTIVE — Phase 7+ mesh transport not yet implemented.

## Why this matters

Spec v0.4 row 28 locks the compression pipeline contract. Sandbox G is the bandwidth half of that contract; sandbox H is the activation-transfer half. Together they validate that OCM's mesh stays cheap on residential internet.

## Source

Spec v0.4 row 28 + research note `docs/superpowers/research/2026-05-09-encryption-compression-optimizations.md`.
