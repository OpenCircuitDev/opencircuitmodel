# Sandbox I: Mem0 Encryption Overhead

**Hypothesis:** SQLCipher AES-256 with Argon2id-derived key adds ≤15% latency overhead on Mem0 retrieval, no measurable accuracy regression.

**Status:** INACTIVE — SQLCipher integration not yet wired into `ocm-memory`.

## Why this matters

Spec v0.4 row 29 names a 5-15% latency overhead range. Sandbox I empirically validates that range under our actual query patterns. If REFUTED on latency, encryption becomes opt-in (off by default) with a documented warning. If REFUTED on accuracy delta, something is structurally wrong with SQLCipher under our access pattern — row 29 needs revising.

This sandbox becomes critical when OCM ships on remote VMs (per spec row 31) — Zone A encryption stops being defense-in-depth and becomes load-bearing.

## Source

Spec v0.4 row 29 + research note `docs/superpowers/research/2026-05-09-encryption-compression-optimizations.md`.
