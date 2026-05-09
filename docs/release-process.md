# OCM Release Process

## How releases work

OCM uses GitHub Actions to build cross-platform installers when a `v*` tag is pushed. The workflow at [`.github/workflows/release.yml`](../.github/workflows/release.yml) builds:

| Platform | Artifact | Notes |
|---|---|---|
| macOS aarch64 | `OpenCircuitModel_<version>_aarch64.dmg` | M1/M2/M3/M4 |
| macOS x86_64 | `OpenCircuitModel_<version>_x64.dmg` | Intel Macs (rare; deprecate later) |
| Windows x86_64 | `OpenCircuitModel_<version>_x64.msi` | WiX-built installer |
| Linux x86_64 | `ocm_<version>_amd64.deb` + `OpenCircuitModel_<version>_amd64.AppImage` | Debian/Ubuntu + portable |

## Cutting a release

```bash
# 1. Update version everywhere version is hard-coded
#    - Cargo.toml workspace.package.version
#    - frontend/package.json
#    - crates/ocm-daemon/tauri.conf.json
git commit -am "chore(release): bump to v0.X.0"

# 2. Tag and push
git tag v0.X.0
git push origin v0.X.0

# 3. The release.yml workflow runs automatically; artifacts upload to a
#    DRAFT GitHub Release. Review draft, edit notes, click Publish.
```

A manual `workflow_dispatch` trigger is also wired so you can produce test
artifacts without cutting a real release. They upload as workflow artifacts
(14-day retention) instead of attaching to a release.

## What's NOT in v1

- **Code signing.** Apple Developer ID + Windows Authenticode certs cost
  money and require organizational identity verification. Spec v0.4 lock:
  signing lands in v4 ("Public Bootnet + Codesigned Daemon"). Until then,
  install instructions document the OS warnings.
- **Auto-update.** Tauri's built-in updater requires signed builds; deferred
  with codesigning to v4.
- **Linux RPM / Flatpak / AppImage signing.** AppImage produced unsigned.
  Flatpak and RPM packaging deferred to community contributors.

## Verifying a build locally

If you have Rust + Node + the platform-native build deps:

```bash
cd crates/ocm-daemon
cargo tauri build
# Artifacts land under target/release/bundle/{dmg,msi,deb,appimage}/
```

Cross-compilation is not officially supported (Tauri's native deps make it
painful). Each platform builds for itself in CI.

## Pre-flight checks before tagging

The release workflow itself runs the production build, but it doesn't run
the test suite. Before tagging, make sure:

```bash
cargo test --workspace          # Rust tests
cd frontend && npm run check    # svelte-check + tsc
cd frontend && npm run build    # adapter-static build
```

All three should pass cleanly.
