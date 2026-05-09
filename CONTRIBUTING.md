# Contributing to OpenCircuitModel

Thanks for being interested. OCM is a free, Apache-2.0 OSS project — every contribution is welcome and material to whether the mission lands.

## Before you start

- **Read [`README.md`](README.md)** for what's built, what's not, and the realistic outcome distribution. OCM is a 24-month bet on mission + learning + optionality. Contribute because you want the mission to land, not because you expect financial return.
- **Read [`docs/superpowers/specs/2026-05-08-ocm-v1-design-spec.md`](docs/superpowers/specs/2026-05-08-ocm-v1-design-spec.md)** for the 31 locked decisions that shape every architecture choice. If your contribution conflicts with a locked decision, raise an issue first — the decision may need revising, but it shouldn't get silently overridden.
- **Skim [`docs/superpowers/plans/2026-05-08-ocm-v1-implementation-plan.md`](docs/superpowers/plans/2026-05-08-ocm-v1-implementation-plan.md)** if you're picking up scoped implementation tasks.

## Areas

### Daemon + API (Rust workspace)

`crates/` holds the seven workspace members:

| Crate | What | Where to start |
|---|---|---|
| `ocm-daemon` | Tauri shell, system tray, settings, supervisor, Tauri commands | `crates/ocm-daemon/src/` |
| `ocm-api` | OpenAI-compat HTTP + auth middleware | `crates/ocm-api/src/lib.rs` |
| `ocm-inference` | InferenceBackend trait + adapters | `crates/ocm-inference/src/lib.rs` |
| `ocm-memory` | Mem0 client | `crates/ocm-memory/src/client.rs` |
| `ocm-mcp` | MCP stdio JSON-RPC bridge | `crates/ocm-mcp/src/main.rs` |
| `ocm-models` | Curated registry + downloader | `crates/ocm-models/src/lib.rs` |
| `ocm-mesh` | v2 transport scaffold (stubs) | `crates/ocm-mesh/src/lib.rs` |

Required:
- Rust 1.78+ (`rustup default stable`)
- For Linux/Tauri builds: `libwebkit2gtk-4.1-dev libssl-dev libgtk-3-dev libayatana-appindicator3-dev librsvg2-dev`

Local check loop:
```bash
cargo fmt --all -- --check
cargo clippy --workspace --all-targets -- -D warnings
cargo test --workspace
```

CI runs the same three on ubuntu / macos / windows. The path filter on `.github/workflows/ci.yml` skips Rust CI for non-Rust PRs — so a docs-only PR doesn't burn ~20 min of matrix runtime.

### Frontend (`frontend/`, SvelteKit + Tailwind v4)

Required:
- Node 20+

Local check loop:
```bash
cd frontend
npm install
npm run check    # svelte-check + tsc
npm run build    # adapter-static -> build/
```

Dev server with HMR + daemon proxy: `npm run dev` (http://localhost:5173). Vite proxies `/v1/*` to `127.0.0.1:7300` so the chat / models pages work against a running daemon. Settings page requires the Tauri build (Tauri commands need the runtime).

### Bench framework (`bench/`)

Hypothesis-based sandbox runner. Each sandbox lives in `bench/isolation/<category>/<sandbox-name>/` with at minimum:

- `expected.json` — the hypothesis, metric, thresholds, decision rule
- `README.md` — what it measures, what it doesn't, how to interpret verdicts

Adding a new sandbox: pick a category (`inference-engines/`, `mesh-transport/`, etc.), copy an existing `expected.json` as a template, write a clear hypothesis with confirm/refute thresholds. Sandboxes that depend on unbuilt features (mesh transport, real model hashes) ship as INACTIVE — the slot gets committed early so the harness has a target later.

### Spec / research / docs

Critical reading is always high-leverage. Flag where the analysis is wrong, the assumptions are off, or the architecture has a hidden flaw. File issues at <https://github.com/OpenCircuitDev/opencircuitmodel/issues>. New research notes go in `docs/superpowers/research/YYYY-MM-DD-<topic>.md`.

## Workflow

1. **Open an issue** before non-trivial code work, especially if it touches a locked decision or adds a new crate. Lightweight design discussion saves PR churn.
2. **Branch off `main`** with a descriptive prefix: `feat/`, `fix/`, `docs/`, `ci/`, or `chore/`.
3. **Keep PRs focused.** One concern per PR. Stack only when changes genuinely depend on each other.
4. **Follow the existing commit-message style:** `<type>(<scope>): <imperative one-line>`. Body explains the *why*, not the *what*. Examples in `git log main`.
5. **CI must be green.** PRs are squash-merged — fmt, clippy, tests, frontend check + build, and any Tauri bundle validation must all pass.
6. **No force pushes** to long-lived branches. Stack maintenance via cherry-picks; let CI rerun.

## What we don't accept

- Commits that bypass `cargo fmt --check` or clippy `-D warnings`. If your editor doesn't auto-format on save, run the checks before pushing.
- Code that conflicts with a locked spec decision without an accompanying issue + design discussion.
- Dependencies that aren't already in the workspace `Cargo.toml` — adding a new dep needs a one-line justification in the PR body.
- Crates that depend on third-party services we haven't vetted. The spec lists every external service we trust (Mem0, llama.cpp, vLLM, iroh, etc.); new ones need an explicit decision row.

## Code of conduct

Be honest, be kind, and assume good intent. If a contribution feedback round gets unproductive, take a day. The project is more important than any single dispute.

## Licensing

By contributing, you agree your contributions are licensed under [Apache 2.0](LICENSE), the project license. No CLA — Apache 2.0's contributor terms are sufficient.

## Reporting security issues

Don't file public issues for security concerns. Email **becky@nativeteachingaids.com** with the details. We'll respond within 72 hours.

## Acknowledgments

OCM stands on the shoulders of every project in [`README.md`'s Acknowledgments](README.md#acknowledgments). When your contribution touches a borrowed framework's surface area, credit the upstream in the commit body.
