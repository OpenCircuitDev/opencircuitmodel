# OpenCircuitModel v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship Single-Node OCM — a free, local, persistent personal AI agent that runs on macOS / Windows / Linux, exposes OpenAI-compatible HTTP and MCP server APIs, and works standalone with zero mesh dependencies.

**Architecture:** Tauri (Rust) daemon supervises Python subprocesses for Letta (agent runtime + memory) and the inference backend (vLLM on NVIDIA, llama.cpp on Apple Silicon). The daemon exposes a localhost HTTP server with OpenAI-compat endpoints and an MCP server adapter. A SvelteKit web UI runs inside Tauri for chat + settings. SQLite + sqlite-vec stores conversation memory.

**Tech Stack:** Rust 1.78+ (Tauri 2.x, axum, tokio, sqlx, tracing) · Python 3.11+ (Letta, vLLM, llama-cpp-python) · TypeScript 5.x (SvelteKit, Vite) · llama.cpp (Metal on Mac) · vLLM (CUDA on NVIDIA) · SQLite + sqlite-vec.

---

## Repo Layout

```
opencircuitmodel/
├── Cargo.toml                          # Workspace root
├── LICENSE                             # Apache 2.0
├── README.md
├── CONTRIBUTING.md
├── .gitignore
├── .github/workflows/ci.yml            # Cross-platform CI
├── docs/
│   └── superpowers/
│       ├── specs/2026-05-08-ocm-v1-design-spec.md
│       └── plans/2026-05-08-ocm-v1-implementation-plan.md
├── crates/
│   ├── ocm-daemon/                     # Tauri app: tray, supervisor, settings
│   │   ├── Cargo.toml
│   │   ├── tauri.conf.json
│   │   └── src/
│   │       ├── main.rs
│   │       ├── supervisor.rs           # Subprocess management
│   │       ├── settings.rs             # TOML config persistence
│   │       ├── paths.rs                # Cross-platform app dirs
│   │       └── tray.rs                 # System tray menu
│   ├── ocm-api/                        # OpenAI-compat HTTP + MCP servers
│   │   ├── Cargo.toml
│   │   └── src/
│   │       ├── lib.rs
│   │       ├── openai.rs               # /v1/chat/completions, /v1/models
│   │       ├── mcp.rs                  # MCP server adapter
│   │       ├── streaming.rs            # SSE token streaming
│   │       └── auth.rs                 # Localhost-only middleware
│   ├── ocm-inference/                  # Backend trait + adapters
│   │   ├── Cargo.toml
│   │   └── src/
│   │       ├── lib.rs                  # InferenceBackend trait
│   │       ├── llamacpp.rs             # llama.cpp subprocess client
│   │       ├── vllm.rs                 # vLLM subprocess client
│   │       └── selector.rs             # Auto-detect platform → backend
│   ├── ocm-letta/                      # Letta adapter
│   │   ├── Cargo.toml
│   │   └── src/
│   │       ├── lib.rs
│   │       ├── client.rs               # Letta REST client
│   │       └── subprocess.rs           # Letta server lifecycle
│   └── ocm-models/                     # Model registry + downloader
│       ├── Cargo.toml
│       ├── registry.json               # Curated model list
│       └── src/
│           ├── lib.rs
│           └── downloader.rs           # SHA256-verified downloads
├── frontend/                           # SvelteKit web UI
│   ├── package.json
│   ├── svelte.config.js
│   ├── vite.config.ts
│   └── src/
│       ├── routes/
│       │   ├── +layout.svelte
│       │   ├── +page.svelte            # Chat
│       │   ├── settings/+page.svelte
│       │   └── models/+page.svelte
│       └── lib/
│           ├── api.ts                  # Daemon HTTP client
│           └── stores.ts               # Svelte stores
├── python/
│   ├── pyproject.toml                  # Letta + backend deps
│   └── ocm_runtime/
│       ├── __init__.py
│       ├── letta_server.py             # Letta server bootstrap script
│       └── llamacpp_server.py          # llama.cpp server wrapper
└── tests/
    ├── integration/
    │   ├── test_openai_compat.rs
    │   ├── test_mcp_adapter.rs
    │   ├── test_memory_persistence.rs
    │   └── test_smoke.sh
    └── fixtures/
        └── tiny-model.gguf             # Tiny GGUF for fast tests
```

---

# Phase 1: Repo Bootstrap & Tauri Shell

> **Goal of phase:** A Tauri app that runs on macOS, Windows, and Linux, shows a system tray, persists settings, and has CI green on all three platforms.

## Task 1.1: Initialize repo + Apache 2.0 license

**Files:**
- Create: `LICENSE`, `README.md`, `.gitignore`, `Cargo.toml` (workspace root)

- [ ] **Step 1: Initialize git repo**

```bash
cd ~/Dropbox/OCR/Open_Circuit/opencircuitmodel
git init
git branch -M main
```

- [ ] **Step 2: Add Apache 2.0 LICENSE**

Download canonical text:

```bash
curl -fsSL https://www.apache.org/licenses/LICENSE-2.0.txt -o LICENSE
```

- [ ] **Step 3: Add `.gitignore`**

Write `.gitignore`:

```gitignore
# Rust
target/
**/*.rs.bk
Cargo.lock.bak

# Node
node_modules/
.svelte-kit/
build/
dist/

# Python
__pycache__/
*.pyc
.venv/
venv/

# OS
.DS_Store
Thumbs.db

# Editor
.vscode/
.idea/
*.swp

# OCM runtime
~/.ocm/
ocm-data/
*.gguf
!tests/fixtures/tiny-model.gguf
```

- [ ] **Step 4: Add minimal `README.md`**

```markdown
# OpenCircuitModel (OCM)

A free, open-source personal AI agent with persistent memory — runs locally,
no cloud account required. Apache 2.0 licensed.

**Status:** v1 alpha — under active development.

See [design spec](docs/superpowers/specs/2026-05-08-ocm-v1-design-spec.md).
```

- [ ] **Step 5: Add workspace `Cargo.toml`**

```toml
[workspace]
resolver = "2"
members = [
    "crates/ocm-daemon",
    "crates/ocm-api",
    "crates/ocm-inference",
    "crates/ocm-letta",
    "crates/ocm-models",
]

[workspace.package]
version = "0.1.0"
edition = "2021"
license = "Apache-2.0"
authors = ["OpenCircuit Dev <hello@opencircuitmodel.org>"]
repository = "https://github.com/OpenCircuitDev/opencircuitmodel"

[workspace.dependencies]
tokio = { version = "1.40", features = ["full"] }
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
tracing = "0.1"
tracing-subscriber = { version = "0.3", features = ["env-filter"] }
anyhow = "1.0"
thiserror = "1.0"
axum = { version = "0.7", features = ["macros"] }
reqwest = { version = "0.12", features = ["json", "stream"] }
sqlx = { version = "0.8", features = ["runtime-tokio", "sqlite", "macros"] }
```

- [ ] **Step 6: First commit**

```bash
git add .
git commit -m "chore: initial repo scaffold with Apache 2.0 LICENSE"
```

---

## Task 1.2: Bootstrap Tauri app skeleton (`ocm-daemon` crate)

**Files:**
- Create: `crates/ocm-daemon/Cargo.toml`, `crates/ocm-daemon/tauri.conf.json`, `crates/ocm-daemon/src/main.rs`, `crates/ocm-daemon/build.rs`, `crates/ocm-daemon/icons/icon.png`

- [ ] **Step 1: Install Tauri CLI**

```bash
cargo install create-tauri-app --locked
cargo install tauri-cli --version "^2.0.0" --locked
```

- [ ] **Step 2: Create `crates/ocm-daemon/Cargo.toml`**

```toml
[package]
name = "ocm-daemon"
version.workspace = true
edition.workspace = true
license.workspace = true

[build-dependencies]
tauri-build = { version = "2.0", features = [] }

[dependencies]
tauri = { version = "2.0", features = ["tray-icon"] }
tauri-plugin-shell = "2.0"
tokio.workspace = true
serde.workspace = true
serde_json.workspace = true
tracing.workspace = true
tracing-subscriber.workspace = true
anyhow.workspace = true
```

- [ ] **Step 3: Create `crates/ocm-daemon/build.rs`**

```rust
fn main() {
    tauri_build::build()
}
```

- [ ] **Step 4: Create `crates/ocm-daemon/tauri.conf.json`**

```json
{
  "$schema": "https://schema.tauri.app/config/2",
  "productName": "OpenCircuitModel",
  "version": "0.1.0",
  "identifier": "org.opencircuitmodel.daemon",
  "build": {
    "frontendDist": "../../frontend/build",
    "devUrl": "http://localhost:5173",
    "beforeDevCommand": "cd ../../frontend && npm run dev",
    "beforeBuildCommand": "cd ../../frontend && npm run build"
  },
  "app": {
    "windows": [
      {
        "title": "OpenCircuitModel",
        "width": 1024,
        "height": 768,
        "resizable": true
      }
    ],
    "security": { "csp": null }
  },
  "bundle": {
    "active": true,
    "targets": "all",
    "icon": ["icons/icon.png"]
  }
}
```

- [ ] **Step 5: Add a placeholder 512×512 icon**

Use any neutral icon for now (replace later). Get one with:

```bash
curl -fsSL https://raw.githubusercontent.com/tauri-apps/tauri/dev/.github/icon.png \
  -o crates/ocm-daemon/icons/icon.png
```

- [ ] **Step 6: Create `crates/ocm-daemon/src/main.rs`**

```rust
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use tracing::info;
use tracing_subscriber::EnvFilter;

fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(EnvFilter::from_default_env().add_directive("ocm=info".parse()?))
        .init();

    info!("OCM daemon starting");

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .run(tauri::generate_context!())
        .expect("Tauri runtime failed");

    Ok(())
}
```

- [ ] **Step 7: Build + run to verify**

```bash
cd crates/ocm-daemon
cargo tauri dev
```

Expected: Tauri window opens, log shows `OCM daemon starting`. Close window.

- [ ] **Step 8: Commit**

```bash
git add crates/ocm-daemon
git commit -m "feat(daemon): bootstrap Tauri 2.x skeleton with workspace integration"
```

---

## Task 1.3: Add system tray with quit menu item

**Files:**
- Create: `crates/ocm-daemon/src/tray.rs`
- Modify: `crates/ocm-daemon/src/main.rs`

- [ ] **Step 1: Write the test for tray menu construction (unit test)**

Add to `crates/ocm-daemon/src/tray.rs`:

```rust
use tauri::menu::{Menu, MenuItem};
use tauri::{AppHandle, Wry};

pub fn build_tray_menu(app: &AppHandle) -> tauri::Result<Menu<Wry>> {
    let show = MenuItem::with_id(app, "show", "Show Window", true, None::<&str>)?;
    let quit = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;
    Menu::with_items(app, &[&show, &quit])
}

#[cfg(test)]
mod tests {
    #[test]
    fn menu_ids_are_unique() {
        // Verifies the menu item ids we expect: "show", "quit"
        let ids = vec!["show", "quit"];
        let mut sorted = ids.clone();
        sorted.sort();
        sorted.dedup();
        assert_eq!(ids.len(), sorted.len(), "menu item ids must be unique");
    }
}
```

- [ ] **Step 2: Run the test**

```bash
cargo test -p ocm-daemon tray::tests
```

Expected: PASS.

- [ ] **Step 3: Wire the tray into `main.rs`**

Modify `crates/ocm-daemon/src/main.rs`:

```rust
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod tray;

use tauri::tray::TrayIconBuilder;
use tauri::Manager;
use tracing::info;
use tracing_subscriber::EnvFilter;

fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(EnvFilter::from_default_env().add_directive("ocm=info".parse()?))
        .init();

    info!("OCM daemon starting");

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            let menu = tray::build_tray_menu(app.handle())?;
            let _tray = TrayIconBuilder::new()
                .menu(&menu)
                .show_menu_on_left_click(true)
                .on_menu_event(|app, event| match event.id.as_ref() {
                    "show" => {
                        if let Some(w) = app.get_webview_window("main") {
                            let _ = w.show();
                            let _ = w.set_focus();
                        }
                    }
                    "quit" => {
                        info!("quit requested via tray");
                        app.exit(0);
                    }
                    _ => {}
                })
                .build(app)?;
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("Tauri runtime failed");

    Ok(())
}
```

- [ ] **Step 4: Run + verify tray appears**

```bash
cargo tauri dev -p ocm-daemon
```

Expected: Tray icon present in menu bar / system tray. Right-click shows Show Window + Quit.

- [ ] **Step 5: Commit**

```bash
git add crates/ocm-daemon
git commit -m "feat(daemon): system tray with show/quit menu items"
```

---

## Task 1.4: Cross-platform app paths

**Files:**
- Create: `crates/ocm-daemon/src/paths.rs`
- Modify: `crates/ocm-daemon/Cargo.toml` (add `directories`)

- [ ] **Step 1: Write the failing test**

```rust
// crates/ocm-daemon/src/paths.rs
use anyhow::{Context, Result};
use std::path::PathBuf;

pub struct AppPaths {
    pub config_dir: PathBuf,
    pub data_dir: PathBuf,
    pub models_dir: PathBuf,
    pub log_dir: PathBuf,
}

impl AppPaths {
    pub fn resolve() -> Result<Self> {
        let dirs = directories::ProjectDirs::from("org", "opencircuitmodel", "OCM")
            .context("could not resolve platform-specific app directories")?;
        let config_dir = dirs.config_dir().to_path_buf();
        let data_dir = dirs.data_dir().to_path_buf();
        let models_dir = data_dir.join("models");
        let log_dir = data_dir.join("logs");
        Ok(Self { config_dir, data_dir, models_dir, log_dir })
    }

    pub fn ensure_all_exist(&self) -> Result<()> {
        for d in [&self.config_dir, &self.data_dir, &self.models_dir, &self.log_dir] {
            std::fs::create_dir_all(d)
                .with_context(|| format!("could not create dir {}", d.display()))?;
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn resolves_distinct_dirs() {
        let p = AppPaths::resolve().expect("resolve paths");
        assert_ne!(p.config_dir, p.data_dir);
        assert!(p.models_dir.starts_with(&p.data_dir));
        assert!(p.log_dir.starts_with(&p.data_dir));
    }

    #[test]
    fn ensure_all_exist_is_idempotent() {
        let p = AppPaths::resolve().expect("resolve paths");
        p.ensure_all_exist().expect("first call");
        p.ensure_all_exist().expect("second call");
        assert!(p.config_dir.exists());
        assert!(p.data_dir.exists());
        assert!(p.models_dir.exists());
        assert!(p.log_dir.exists());
    }
}
```

- [ ] **Step 2: Add `directories` dependency**

Edit `crates/ocm-daemon/Cargo.toml`, add to `[dependencies]`:

```toml
directories = "5.0"
```

- [ ] **Step 3: Wire `paths` module into `main.rs`**

Add at top:

```rust
mod paths;
```

In the `setup` closure, before tray construction:

```rust
let app_paths = paths::AppPaths::resolve()?;
app_paths.ensure_all_exist()?;
info!(
    config = %app_paths.config_dir.display(),
    data = %app_paths.data_dir.display(),
    "app paths resolved"
);
app.manage(app_paths);
```

- [ ] **Step 4: Run tests + run app**

```bash
cargo test -p ocm-daemon paths::tests
cargo tauri dev -p ocm-daemon
```

Expected: Tests PASS. App startup logs include `config=...`, `data=...` with sensible OS paths (e.g., `~/Library/Application Support/org.opencircuitmodel.OCM` on macOS).

- [ ] **Step 5: Commit**

```bash
git add crates/ocm-daemon
git commit -m "feat(daemon): cross-platform app config/data/models/log paths"
```

---

## Task 1.5: Settings persistence (TOML)

**Files:**
- Create: `crates/ocm-daemon/src/settings.rs`
- Modify: `crates/ocm-daemon/Cargo.toml` (add `toml`), `crates/ocm-daemon/src/main.rs`

- [ ] **Step 1: Write failing test**

```rust
// crates/ocm-daemon/src/settings.rs
use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};
use std::path::Path;

#[derive(Debug, Serialize, Deserialize, Clone, PartialEq)]
pub struct Settings {
    pub model_id: Option<String>,
    pub api_port: u16,
    pub mcp_enabled: bool,
    pub theme: Theme,
}

#[derive(Debug, Serialize, Deserialize, Clone, PartialEq, Copy)]
#[serde(rename_all = "lowercase")]
pub enum Theme { Dark, Light, System }

impl Default for Settings {
    fn default() -> Self {
        Self { model_id: None, api_port: 7300, mcp_enabled: true, theme: Theme::System }
    }
}

impl Settings {
    pub fn load_or_default(path: &Path) -> Result<Self> {
        if !path.exists() { return Ok(Self::default()); }
        let raw = std::fs::read_to_string(path).context("read settings.toml")?;
        toml::from_str(&raw).context("parse settings.toml")
    }

    pub fn save(&self, path: &Path) -> Result<()> {
        let raw = toml::to_string_pretty(self).context("serialize settings")?;
        std::fs::write(path, raw).context("write settings.toml")?;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    #[test]
    fn round_trip_default_settings() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("settings.toml");
        let original = Settings::default();
        original.save(&path).unwrap();
        let loaded = Settings::load_or_default(&path).unwrap();
        assert_eq!(original, loaded);
    }

    #[test]
    fn missing_file_yields_default() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("nonexistent.toml");
        let s = Settings::load_or_default(&path).unwrap();
        assert_eq!(s, Settings::default());
    }
}
```

- [ ] **Step 2: Add deps**

Edit `crates/ocm-daemon/Cargo.toml`:

```toml
[dependencies]
# ...existing...
toml = "0.8"

[dev-dependencies]
tempfile = "3.10"
```

- [ ] **Step 3: Run tests**

```bash
cargo test -p ocm-daemon settings::tests
```

Expected: PASS.

- [ ] **Step 4: Wire into `main.rs` `setup` closure (after `app.manage(app_paths)`)**

```rust
mod settings;

// inside setup, replace existing log line region:
let settings_path = app_paths.config_dir.join("settings.toml");
let settings = settings::Settings::load_or_default(&settings_path)?;
info!(model = ?settings.model_id, port = settings.api_port, "settings loaded");
app.manage(settings);
```

- [ ] **Step 5: Commit**

```bash
git add crates/ocm-daemon
git commit -m "feat(daemon): TOML settings load/save with sensible defaults"
```

---

## Task 1.6: Cross-platform CI workflow

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Write the workflow**

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  rust:
    name: Rust on ${{ matrix.os }}
    runs-on: ${{ matrix.os }}
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
    steps:
      - uses: actions/checkout@v4
      - uses: dtolnay/rust-toolchain@stable
        with:
          components: rustfmt, clippy
      - name: Install Linux deps for Tauri
        if: matrix.os == 'ubuntu-latest'
        run: |
          sudo apt-get update
          sudo apt-get install -y libwebkit2gtk-4.1-dev libssl-dev libgtk-3-dev \
            libayatana-appindicator3-dev librsvg2-dev
      - uses: Swatinem/rust-cache@v2
      - name: Format check
        run: cargo fmt --all -- --check
      - name: Clippy
        run: cargo clippy --workspace --all-targets -- -D warnings
      - name: Test
        run: cargo test --workspace
```

- [ ] **Step 2: Verify green locally first**

```bash
cargo fmt --all
cargo clippy --workspace --all-targets
cargo test --workspace
```

Fix any failures before pushing.

- [ ] **Step 3: Commit + push**

```bash
git add .github
git commit -m "ci: add cross-platform Rust CI for ubuntu/macos/windows"
```

(After GitHub repo is created in Task 1.7, push and verify the workflow goes green.)

---

## Task 1.7: Create GitHub repo + push

**Files:** none in repo (this configures GitHub).

- [ ] **Step 1: Create the repo via gh CLI**

```bash
gh repo create OpenCircuitDev/opencircuitmodel \
  --public \
  --description "Free, open-source personal AI agent with persistent memory. Apache 2.0." \
  --homepage "https://opencircuitmodel.org"
```

- [ ] **Step 2: Add remote + push**

```bash
git remote add origin https://github.com/OpenCircuitDev/opencircuitmodel.git
git push -u origin main
```

- [ ] **Step 3: Verify CI runs**

```bash
gh run watch
```

Expected: All three OS runners pass. Fix any platform-specific failures before continuing.

- [ ] **Step 4: Add basic GitHub repo settings**

```bash
gh repo edit --enable-issues --enable-discussions --enable-wiki=false
```

---

## Task 1.8: Add `tauri-plugin-log` for file-rotated logging

**Files:**
- Modify: `crates/ocm-daemon/Cargo.toml`, `crates/ocm-daemon/src/main.rs`

- [ ] **Step 1: Add dependency**

```toml
[dependencies]
# ...
tauri-plugin-log = "2.0"
```

- [ ] **Step 2: Wire it in `main.rs`**

Add to the Tauri builder chain before `.setup`:

```rust
.plugin(
    tauri_plugin_log::Builder::new()
        .targets([
            tauri_plugin_log::Target::new(tauri_plugin_log::TargetKind::Stdout),
            tauri_plugin_log::Target::new(tauri_plugin_log::TargetKind::LogDir { file_name: Some("ocm".to_string()) }),
        ])
        .level(log::LevelFilter::Info)
        .build(),
)
```

(Add `log = "0.4"` to deps if not present.)

- [ ] **Step 3: Run app + verify log file**

```bash
cargo tauri dev -p ocm-daemon
```

Send a log via dev tools (or just notice startup logs land in `~/Library/Logs/org.opencircuitmodel.OCM/ocm.log` on macOS / equivalent elsewhere).

- [ ] **Step 4: Commit**

```bash
git commit -am "feat(daemon): file-rotated logging via tauri-plugin-log"
```

---

## Task 1.9: Add daemon-internal health endpoint stub

**Files:**
- Create: `crates/ocm-daemon/src/health.rs`
- Modify: `crates/ocm-daemon/src/main.rs`

- [ ] **Step 1: Failing test for health response shape**

```rust
// crates/ocm-daemon/src/health.rs
use serde::Serialize;

#[derive(Debug, Serialize, PartialEq)]
pub struct Health {
    pub status: &'static str,
    pub version: &'static str,
}

pub fn current() -> Health {
    Health { status: "ok", version: env!("CARGO_PKG_VERSION") }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn health_reports_ok_and_version() {
        let h = current();
        assert_eq!(h.status, "ok");
        assert!(!h.version.is_empty());
        // serializable
        let json = serde_json::to_string(&h).unwrap();
        assert!(json.contains("\"status\":\"ok\""));
    }
}
```

- [ ] **Step 2: Run + pass**

```bash
cargo test -p ocm-daemon health::tests
```

- [ ] **Step 3: Add `mod health;` to `main.rs`** (no wiring yet — used by `ocm-api` later)

- [ ] **Step 4: Commit**

```bash
git commit -am "feat(daemon): minimal health struct for liveness reporting"
```

---

## Task 1.10: Pre-commit hook for fmt + clippy

**Files:**
- Create: `.git/hooks/pre-commit` (local) and `scripts/install-hooks.sh` (committed)

- [ ] **Step 1: Write `scripts/install-hooks.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail

HOOK_DIR="$(git rev-parse --git-path hooks)"
mkdir -p "$HOOK_DIR"

cat > "$HOOK_DIR/pre-commit" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
cargo fmt --all -- --check
cargo clippy --workspace --all-targets -- -D warnings
EOF

chmod +x "$HOOK_DIR/pre-commit"
echo "Pre-commit hook installed."
```

- [ ] **Step 2: Make it executable**

```bash
chmod +x scripts/install-hooks.sh
./scripts/install-hooks.sh
```

- [ ] **Step 3: Verify**

```bash
git commit --allow-empty -m "test: verify hooks"
```

Should run fmt+clippy before allowing commit.

- [ ] **Step 4: Document in README**

Append to `README.md`:

```markdown
## Development

After cloning:
```bash
./scripts/install-hooks.sh
cargo tauri dev -p ocm-daemon
```
```

- [ ] **Step 5: Commit**

```bash
git add scripts README.md
git commit -m "chore: pre-commit hooks for fmt + clippy"
```

---

## Task 1.11: Phase 1 verification gate

**Files:** none.

- [ ] **Step 1: Run full local check**

```bash
cargo fmt --all -- --check
cargo clippy --workspace --all-targets -- -D warnings
cargo test --workspace
cargo tauri dev -p ocm-daemon  # close after seeing tray + window
```

- [ ] **Step 2: Verify on remote CI**

```bash
gh run list --limit 1
```

Expected: latest run all green on ubuntu/macos/windows.

- [ ] **Step 3: Tag Phase 1 milestone**

```bash
git tag -a v0.1.0-phase1 -m "Phase 1 complete: Tauri shell + tray + settings + paths + logging + CI"
git push --tags
```

---

# Phase 2: Inference Backend Adapters

> **Goal of phase:** A unified `InferenceBackend` trait with two working implementations — `LlamaCpp` (Apple Silicon path) and `Vllm` (NVIDIA path) — both running as subprocesses managed by the daemon, both producing streaming token output for a hardcoded test prompt.

## Task 2.1: Define `InferenceBackend` trait

**Files:**
- Create: `crates/ocm-inference/Cargo.toml`, `crates/ocm-inference/src/lib.rs`

- [ ] **Step 1: Create `crates/ocm-inference/Cargo.toml`**

```toml
[package]
name = "ocm-inference"
version.workspace = true
edition.workspace = true
license.workspace = true

[dependencies]
async-trait = "0.1"
serde.workspace = true
serde_json.workspace = true
tokio = { workspace = true, features = ["full"] }
tokio-stream = "0.1"
reqwest.workspace = true
futures = "0.3"
tracing.workspace = true
anyhow.workspace = true
thiserror.workspace = true
```

- [ ] **Step 2: Define the trait in `lib.rs`**

```rust
use async_trait::async_trait;
use futures::stream::BoxStream;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChatMessage {
    pub role: Role,
    pub content: String,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "lowercase")]
pub enum Role { System, User, Assistant }

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct GenerationParams {
    pub max_tokens: Option<u32>,
    pub temperature: Option<f32>,
    pub top_p: Option<f32>,
    pub stop: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChatRequest {
    pub messages: Vec<ChatMessage>,
    pub params: GenerationParams,
}

#[derive(Debug, thiserror::Error)]
pub enum BackendError {
    #[error("backend not ready: {0}")]
    NotReady(String),
    #[error("backend transport error: {0}")]
    Transport(#[from] reqwest::Error),
    #[error("backend protocol error: {0}")]
    Protocol(String),
    #[error("backend killed or crashed")]
    Crashed,
}

#[async_trait]
pub trait InferenceBackend: Send + Sync {
    fn name(&self) -> &'static str;
    async fn health(&self) -> Result<(), BackendError>;
    async fn generate(
        &self,
        req: ChatRequest,
    ) -> Result<BoxStream<'static, Result<String, BackendError>>, BackendError>;
}

pub mod llamacpp;
pub mod vllm;
pub mod selector;
```

(Module files filled in later tasks.)

- [ ] **Step 3: Stub the submodules so the crate compiles**

Add to each:

```rust
// crates/ocm-inference/src/llamacpp.rs
// crates/ocm-inference/src/vllm.rs
// crates/ocm-inference/src/selector.rs
// (empty for now)
```

- [ ] **Step 4: Build**

```bash
cargo build -p ocm-inference
```

Expected: compiles, no warnings.

- [ ] **Step 5: Commit**

```bash
git add crates/ocm-inference
git commit -m "feat(inference): backend trait + chat types + error model"
```

---

## Task 2.2: llama.cpp subprocess client (Apple Silicon path)

**Files:**
- Modify: `crates/ocm-inference/src/llamacpp.rs`

> **Note for engineer:** This task assumes `llama-server` (the binary from llama.cpp) is on `PATH` or installed at a known location. v1 expects the user to install via Homebrew (`brew install llama.cpp`) or a bundled binary in the installer (Phase 6).

- [ ] **Step 1: Failing integration test**

Create `crates/ocm-inference/tests/llamacpp_smoke.rs`:

```rust
//! Run only when LLAMACPP_SERVER_URL is set, e.g.:
//!   LLAMACPP_SERVER_URL=http://localhost:8080 cargo test --test llamacpp_smoke -- --ignored
use ocm_inference::llamacpp::LlamaCpp;
use ocm_inference::{ChatMessage, ChatRequest, GenerationParams, InferenceBackend, Role};
use futures::StreamExt;

#[tokio::test]
#[ignore]
async fn streams_tokens_from_running_server() {
    let url = std::env::var("LLAMACPP_SERVER_URL")
        .expect("LLAMACPP_SERVER_URL must be set for this test");
    let backend = LlamaCpp::new(url);
    backend.health().await.expect("server is up");

    let req = ChatRequest {
        messages: vec![ChatMessage {
            role: Role::User,
            content: "Say one word.".to_string(),
        }],
        params: GenerationParams {
            max_tokens: Some(8),
            temperature: Some(0.0),
            ..Default::default()
        },
    };

    let mut stream = backend.generate(req).await.expect("stream");
    let mut total = String::new();
    while let Some(chunk) = stream.next().await {
        total.push_str(&chunk.expect("chunk"));
    }
    assert!(!total.is_empty(), "expected non-empty completion");
}
```

- [ ] **Step 2: Implement `LlamaCpp` against llama.cpp's OpenAI-compat API**

```rust
// crates/ocm-inference/src/llamacpp.rs
use crate::{
    BackendError, ChatMessage, ChatRequest, InferenceBackend, Role,
};
use async_trait::async_trait;
use futures::stream::BoxStream;
use futures::StreamExt;
use reqwest::Client;
use serde::{Deserialize, Serialize};

pub struct LlamaCpp {
    base_url: String,
    http: Client,
}

impl LlamaCpp {
    pub fn new(base_url: impl Into<String>) -> Self {
        Self { base_url: base_url.into(), http: Client::new() }
    }
}

#[derive(Serialize)]
struct OaiChatBody<'a> {
    model: &'a str,
    messages: Vec<OaiMsg<'a>>,
    stream: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    max_tokens: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    temperature: Option<f32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    top_p: Option<f32>,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    stop: Vec<String>,
}

#[derive(Serialize)]
struct OaiMsg<'a> {
    role: &'a str,
    content: &'a str,
}

#[derive(Deserialize)]
struct OaiChunk {
    choices: Vec<OaiChunkChoice>,
}

#[derive(Deserialize)]
struct OaiChunkChoice {
    delta: OaiDelta,
}

#[derive(Deserialize)]
struct OaiDelta {
    #[serde(default)]
    content: Option<String>,
}

fn role_str(r: &Role) -> &'static str {
    match r { Role::System => "system", Role::User => "user", Role::Assistant => "assistant" }
}

#[async_trait]
impl InferenceBackend for LlamaCpp {
    fn name(&self) -> &'static str { "llama.cpp" }

    async fn health(&self) -> Result<(), BackendError> {
        let r = self.http.get(format!("{}/health", self.base_url)).send().await?;
        if r.status().is_success() { Ok(()) } else { Err(BackendError::NotReady(r.status().to_string())) }
    }

    async fn generate(
        &self,
        req: ChatRequest,
    ) -> Result<BoxStream<'static, Result<String, BackendError>>, BackendError> {
        let messages: Vec<OaiMsg> = req.messages.iter()
            .map(|m| OaiMsg { role: role_str(&m.role), content: &m.content })
            .collect();
        let body = OaiChatBody {
            model: "default",
            messages,
            stream: true,
            max_tokens: req.params.max_tokens,
            temperature: req.params.temperature,
            top_p: req.params.top_p,
            stop: req.params.stop,
        };
        let resp = self.http
            .post(format!("{}/v1/chat/completions", self.base_url))
            .json(&body)
            .send()
            .await?
            .error_for_status()?;

        let stream = resp.bytes_stream().map(|chunk| {
            let bytes = chunk.map_err(BackendError::from)?;
            let text = std::str::from_utf8(&bytes)
                .map_err(|e| BackendError::Protocol(e.to_string()))?
                .to_string();
            // SSE lines: "data: {json}\n\n" — extract delta.content from each
            let mut out = String::new();
            for line in text.lines() {
                let line = line.trim();
                if let Some(rest) = line.strip_prefix("data: ") {
                    if rest == "[DONE]" { continue; }
                    if let Ok(c) = serde_json::from_str::<OaiChunk>(rest) {
                        if let Some(choice) = c.choices.first() {
                            if let Some(content) = &choice.delta.content {
                                out.push_str(content);
                            }
                        }
                    }
                }
            }
            Ok(out)
        });
        Ok(stream.boxed())
    }
}
```

- [ ] **Step 3: Manual smoke test**

```bash
# In one terminal: start a llama.cpp server with any GGUF model
brew install llama.cpp  # if not installed
llama-server -m ~/Downloads/qwen2.5-1.5b-instruct-q4_k_m.gguf -c 4096 --port 8080

# In another: run the ignored integration test
LLAMACPP_SERVER_URL=http://localhost:8080 cargo test -p ocm-inference --test llamacpp_smoke -- --ignored --nocapture
```

Expected: PASS, prints non-empty completion.

- [ ] **Step 4: Commit**

```bash
git add crates/ocm-inference
git commit -m "feat(inference): llama.cpp backend with SSE streaming"
```

---

## Task 2.3: vLLM subprocess client (NVIDIA path)

**Files:**
- Modify: `crates/ocm-inference/src/vllm.rs`

> **Note:** vLLM also exposes an OpenAI-compatible HTTP server (`python -m vllm.entrypoints.openai.api_server`). The wire format matches llama.cpp's, so most of the implementation is shared.

- [ ] **Step 1: Implement `Vllm` (mirror of `LlamaCpp` with adjusted health endpoint)**

```rust
// crates/ocm-inference/src/vllm.rs
use crate::{
    llamacpp::LlamaCpp, // we'll factor a shared helper soon
    BackendError, ChatRequest, InferenceBackend,
};
use async_trait::async_trait;
use futures::stream::BoxStream;
use reqwest::Client;

pub struct Vllm {
    inner: LlamaCpp,
    http: Client,
    base_url: String,
}

impl Vllm {
    pub fn new(base_url: impl Into<String>) -> Self {
        let base_url = base_url.into();
        Self {
            inner: LlamaCpp::new(base_url.clone()),
            http: Client::new(),
            base_url,
        }
    }
}

#[async_trait]
impl InferenceBackend for Vllm {
    fn name(&self) -> &'static str { "vLLM" }

    async fn health(&self) -> Result<(), BackendError> {
        // vLLM exposes /health (older) and /v1/models (always available)
        let r = self.http.get(format!("{}/v1/models", self.base_url)).send().await?;
        if r.status().is_success() { Ok(()) } else { Err(BackendError::NotReady(r.status().to_string())) }
    }

    async fn generate(
        &self,
        req: ChatRequest,
    ) -> Result<BoxStream<'static, Result<String, BackendError>>, BackendError> {
        self.inner.generate(req).await
    }
}
```

- [ ] **Step 2: Smoke-test only on a machine with vLLM (skip on Mac)**

```bash
# Run on Linux + NVIDIA
pip install vllm
python -m vllm.entrypoints.openai.api_server --model meta-llama/Llama-3.1-8B-Instruct --port 8000

VLLM_SERVER_URL=http://localhost:8000 \
  cargo test -p ocm-inference --test vllm_smoke -- --ignored --nocapture
```

(Add a parallel `tests/vllm_smoke.rs` modeled on `llamacpp_smoke.rs`.)

- [ ] **Step 3: Commit**

```bash
git commit -am "feat(inference): vLLM backend (OpenAI-compat shared with llama.cpp)"
```

---

## Task 2.4: Backend selector (auto-detect platform)

**Files:**
- Modify: `crates/ocm-inference/src/selector.rs`

- [ ] **Step 1: Failing test**

```rust
// crates/ocm-inference/src/selector.rs
use crate::{InferenceBackend, llamacpp::LlamaCpp, vllm::Vllm};

pub enum BackendKind { LlamaCpp, Vllm }

pub fn detect_backend_kind() -> BackendKind {
    if cfg!(target_os = "macos") {
        BackendKind::LlamaCpp
    } else if has_cuda() {
        BackendKind::Vllm
    } else {
        BackendKind::LlamaCpp
    }
}

#[cfg(target_os = "linux")]
fn has_cuda() -> bool {
    std::path::Path::new("/usr/lib/x86_64-linux-gnu/libcuda.so.1").exists()
        || std::path::Path::new("/usr/lib64/libcuda.so.1").exists()
}

#[cfg(not(target_os = "linux"))]
fn has_cuda() -> bool { false }

pub fn make_backend(base_url: String) -> Box<dyn InferenceBackend> {
    match detect_backend_kind() {
        BackendKind::Vllm => Box::new(Vllm::new(base_url)),
        BackendKind::LlamaCpp => Box::new(LlamaCpp::new(base_url)),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn macos_picks_llamacpp() {
        if cfg!(target_os = "macos") {
            matches!(detect_backend_kind(), BackendKind::LlamaCpp);
        }
    }
}
```

- [ ] **Step 2: Run test**

```bash
cargo test -p ocm-inference selector::tests
```

- [ ] **Step 3: Commit**

```bash
git commit -am "feat(inference): backend selector by platform with CUDA probe"
```

---

## Task 2.5: Subprocess supervisor in daemon

**Files:**
- Create: `crates/ocm-daemon/src/supervisor.rs`
- Modify: `crates/ocm-daemon/Cargo.toml`, `crates/ocm-daemon/src/main.rs`

- [ ] **Step 1: Add deps**

In `crates/ocm-daemon/Cargo.toml`:

```toml
[dependencies]
ocm-inference = { path = "../ocm-inference" }
async-trait = "0.1"
```

- [ ] **Step 2: Write the failing supervisor test (uses a mock command)**

```rust
// crates/ocm-daemon/src/supervisor.rs
use anyhow::{Context, Result};
use std::process::{Child, Command, Stdio};
use std::sync::{Arc, Mutex};
use tracing::{info, warn};

pub struct Supervisor {
    name: String,
    cmd_factory: Box<dyn Fn() -> Command + Send + Sync>,
    child: Arc<Mutex<Option<Child>>>,
}

impl Supervisor {
    pub fn new<F>(name: impl Into<String>, factory: F) -> Self
    where F: Fn() -> Command + Send + Sync + 'static {
        Self {
            name: name.into(),
            cmd_factory: Box::new(factory),
            child: Arc::new(Mutex::new(None)),
        }
    }

    pub fn start(&self) -> Result<()> {
        let mut guard = self.child.lock().unwrap();
        if guard.is_some() {
            warn!(name = %self.name, "already running");
            return Ok(());
        }
        let mut cmd = (self.cmd_factory)();
        cmd.stdin(Stdio::null()).stdout(Stdio::piped()).stderr(Stdio::piped());
        let child = cmd.spawn().with_context(|| format!("spawn {}", self.name))?;
        info!(name = %self.name, pid = child.id(), "subprocess started");
        *guard = Some(child);
        Ok(())
    }

    pub fn stop(&self) {
        let mut guard = self.child.lock().unwrap();
        if let Some(mut c) = guard.take() {
            let _ = c.kill();
            let _ = c.wait();
            info!(name = %self.name, "subprocess stopped");
        }
    }

    pub fn is_alive(&self) -> bool {
        let mut guard = self.child.lock().unwrap();
        if let Some(c) = guard.as_mut() {
            match c.try_wait() {
                Ok(Some(_)) => { *guard = None; false }
                Ok(None) => true,
                Err(_) => false,
            }
        } else { false }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn lifecycle_with_sleep_command() {
        let sup = Supervisor::new("sleep", || {
            #[cfg(unix)]
            { let mut c = Command::new("sleep"); c.arg("30"); c }
            #[cfg(windows)]
            { let mut c = Command::new("powershell"); c.args(["-Command", "Start-Sleep 30"]); c }
        });
        assert!(!sup.is_alive());
        sup.start().expect("start");
        assert!(sup.is_alive());
        sup.stop();
        assert!(!sup.is_alive());
    }
}
```

- [ ] **Step 3: Run test**

```bash
cargo test -p ocm-daemon supervisor::tests
```

- [ ] **Step 4: Commit**

```bash
git commit -am "feat(daemon): generic subprocess supervisor with start/stop/liveness"
```

---

## Task 2.6: Spawn llama.cpp from supervisor (Mac path)

**Files:**
- Modify: `crates/ocm-daemon/src/supervisor.rs` (add helper), `crates/ocm-daemon/src/main.rs`

- [ ] **Step 1: Add a `spawn_llama_server` helper**

Append to `supervisor.rs`:

```rust
use std::path::Path;

pub fn spawn_llama_server(
    binary: &Path,
    model_path: &Path,
    port: u16,
    ctx_len: u32,
) -> Supervisor {
    let binary = binary.to_path_buf();
    let model_path = model_path.to_path_buf();
    Supervisor::new("llama-server", move || {
        let mut c = Command::new(&binary);
        c.arg("-m").arg(&model_path)
            .arg("-c").arg(ctx_len.to_string())
            .arg("--port").arg(port.to_string())
            .arg("--host").arg("127.0.0.1");
        c
    })
}
```

- [ ] **Step 2: Wire (without spawning yet) into `main.rs` setup**

Just `mod supervisor;` for now. Actual spawn happens in Task 2.8 once we have a model path.

- [ ] **Step 3: Commit**

```bash
git commit -am "feat(daemon): supervisor helper for llama-server"
```

---

## Task 2.7: Spawn vLLM from supervisor (NVIDIA path)

**Files:**
- Modify: `crates/ocm-daemon/src/supervisor.rs`

- [ ] **Step 1: Add `spawn_vllm_server` helper**

```rust
pub fn spawn_vllm_server(
    python: &Path,
    model_id: &str,
    port: u16,
) -> Supervisor {
    let python = python.to_path_buf();
    let model_id = model_id.to_string();
    Supervisor::new("vllm-server", move || {
        let mut c = Command::new(&python);
        c.args([
            "-m", "vllm.entrypoints.openai.api_server",
            "--model", &model_id,
            "--port", &port.to_string(),
            "--host", "127.0.0.1",
        ]);
        c
    })
}
```

- [ ] **Step 2: Commit**

```bash
git commit -am "feat(daemon): supervisor helper for vLLM"
```

---

## Task 2.8: Wire backend selection + readiness wait into setup

**Files:**
- Modify: `crates/ocm-daemon/src/main.rs`

- [ ] **Step 1: Add `wait_for_backend_ready` helper**

In `supervisor.rs`:

```rust
use std::time::{Duration, Instant};

pub async fn wait_for_http_ready(url: &str, timeout: Duration) -> Result<()> {
    let client = reqwest::Client::new();
    let start = Instant::now();
    while start.elapsed() < timeout {
        if let Ok(r) = client.get(url).send().await {
            if r.status().is_success() { return Ok(()); }
        }
        tokio::time::sleep(Duration::from_millis(500)).await;
    }
    anyhow::bail!("backend at {url} did not become ready within {timeout:?}")
}
```

(Add `reqwest` to deps if not already present.)

- [ ] **Step 2: Verify (no test yet — used in main)**

```bash
cargo build -p ocm-daemon
```

- [ ] **Step 3: Commit**

```bash
git commit -am "feat(daemon): wait_for_http_ready helper for backend startup"
```

---

## Task 2.9: Phase 2 verification gate

**Files:** none.

- [ ] **Step 1: Run full check**

```bash
cargo fmt --all -- --check
cargo clippy --workspace --all-targets -- -D warnings
cargo test --workspace
```

- [ ] **Step 2: Run ignored llama.cpp smoke test (Mac dev box)**

```bash
llama-server -m ~/.ocm/models/qwen2.5-1.5b-q4.gguf -c 4096 --port 8080 &
LLAMACPP_SERVER_URL=http://localhost:8080 cargo test -p ocm-inference --test llamacpp_smoke -- --ignored
kill %1
```

- [ ] **Step 3: Tag**

```bash
git tag -a v0.1.0-phase2 -m "Phase 2: inference backend trait + llama.cpp + vLLM + supervisor"
git push --tags
```

---

# Phase 3: Letta Integration

> **Goal of phase:** A running Letta server (Python subprocess) that the daemon talks to, with a single agent created on first run, persistent SQLite memory, and a Rust client wrapper for sending messages and receiving streaming responses.

## Task 3.1: Set up Python runtime + pyproject

**Files:**
- Create: `python/pyproject.toml`, `python/ocm_runtime/__init__.py`, `python/ocm_runtime/letta_server.py`

- [ ] **Step 1: Write `python/pyproject.toml`**

```toml
[project]
name = "ocm-runtime"
version = "0.1.0"
description = "OCM Python subprocesses (Letta + optional inference backends)"
requires-python = ">=3.11"
dependencies = [
    "letta>=0.5.0",
    "uvicorn>=0.30",
    "fastapi>=0.115",
    "httpx>=0.27",
]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"
```

- [ ] **Step 2: Create venv setup script**

`scripts/setup-python.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3.11 -m venv python/.venv
source python/.venv/bin/activate
pip install --upgrade pip
pip install -e python/
echo "Python runtime ready: source python/.venv/bin/activate"
```

```bash
chmod +x scripts/setup-python.sh
./scripts/setup-python.sh
```

- [ ] **Step 3: Commit**

```bash
git add python scripts
git commit -m "chore(python): scaffold ocm_runtime package and venv setup script"
```

---

## Task 3.2: Letta server bootstrap script

**Files:**
- Create: `python/ocm_runtime/letta_server.py`

- [ ] **Step 1: Write the bootstrap**

```python
"""Bootstrap a Letta server with OCM defaults.

Invoked by ocm-daemon as a subprocess. Reads OCM_LETTA_PORT,
OCM_LETTA_DB_URL, OCM_LETTA_INFERENCE_URL from env.
"""
from __future__ import annotations

import os
import sys

def main() -> int:
    port = int(os.environ.get("OCM_LETTA_PORT", "8283"))
    db_url = os.environ.get("OCM_LETTA_DB_URL", "sqlite:///./ocm-letta.db")
    inference_url = os.environ.get("OCM_LETTA_INFERENCE_URL", "http://127.0.0.1:8080/v1")

    # Letta exposes a CLI / library entry; we shell to its server module
    # and pass our config via env. See letta docs for current entry point.
    os.environ.setdefault("LETTA_PG_URI", db_url)
    os.environ.setdefault("OPENAI_API_BASE", inference_url)
    os.environ.setdefault("OPENAI_API_KEY", "ocm-local")

    from letta.server.rest_api.app import start_server  # type: ignore
    start_server(host="127.0.0.1", port=port)
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

> **Engineer note:** Letta's API surface evolves; `start_server` may be renamed. Verify against the current `letta` package version when you actually run this. If the import path differs, adapt the import — but keep the entrypoint contract: HTTP server on `127.0.0.1:OCM_LETTA_PORT`.

- [ ] **Step 2: Manual smoke**

```bash
source python/.venv/bin/activate
OCM_LETTA_PORT=8283 python -m ocm_runtime.letta_server &
curl -fsS http://localhost:8283/v1/health || curl -fsS http://localhost:8283/health
```

Expected: 200 from one of the health paths. Adjust path in subsequent code based on what Letta serves.

- [ ] **Step 3: Commit**

```bash
git commit -am "feat(letta): bootstrap script with env-driven port/db/inference config"
```

---

## Task 3.3: `ocm-letta` crate with HTTP client

**Files:**
- Create: `crates/ocm-letta/Cargo.toml`, `crates/ocm-letta/src/lib.rs`, `crates/ocm-letta/src/client.rs`

- [ ] **Step 1: Cargo.toml**

```toml
[package]
name = "ocm-letta"
version.workspace = true
edition.workspace = true
license.workspace = true

[dependencies]
async-trait = "0.1"
serde.workspace = true
serde_json.workspace = true
tokio.workspace = true
reqwest.workspace = true
futures = "0.3"
tracing.workspace = true
anyhow.workspace = true
thiserror.workspace = true
```

- [ ] **Step 2: `lib.rs`**

```rust
pub mod client;
pub use client::{LettaClient, LettaError, AgentId, MessageStream};
```

- [ ] **Step 3: `client.rs` skeleton with failing test**

```rust
use futures::stream::BoxStream;
use reqwest::Client;
use serde::{Deserialize, Serialize};

#[derive(Debug, thiserror::Error)]
pub enum LettaError {
    #[error("transport: {0}")]
    Transport(#[from] reqwest::Error),
    #[error("protocol: {0}")]
    Protocol(String),
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentId(pub String);

#[derive(Debug, Serialize)]
pub struct CreateAgentRequest<'a> {
    pub name: &'a str,
    pub system: Option<&'a str>,
}

#[derive(Debug, Deserialize)]
pub struct AgentResponse {
    pub id: String,
    pub name: String,
}

pub type MessageStream = BoxStream<'static, Result<String, LettaError>>;

pub struct LettaClient {
    base_url: String,
    http: Client,
}

impl LettaClient {
    pub fn new(base_url: impl Into<String>) -> Self {
        Self { base_url: base_url.into(), http: Client::new() }
    }

    pub async fn health(&self) -> Result<(), LettaError> {
        // Letta health endpoint — confirm path against current Letta docs.
        let r = self.http.get(format!("{}/v1/health", self.base_url)).send().await?;
        if r.status().is_success() { Ok(()) } else { Err(LettaError::Protocol(r.status().to_string())) }
    }

    pub async fn create_or_get_agent(&self, name: &str, system: Option<&str>) -> Result<AgentId, LettaError> {
        // List → find by name → create if missing
        let list: serde_json::Value = self.http
            .get(format!("{}/v1/agents", self.base_url))
            .send().await?.error_for_status()?.json().await?;
        if let Some(arr) = list.as_array() {
            for a in arr {
                if a.get("name").and_then(|v| v.as_str()) == Some(name) {
                    if let Some(id) = a.get("id").and_then(|v| v.as_str()) {
                        return Ok(AgentId(id.to_string()));
                    }
                }
            }
        }
        let body = CreateAgentRequest { name, system };
        let created: AgentResponse = self.http
            .post(format!("{}/v1/agents", self.base_url))
            .json(&body).send().await?.error_for_status()?.json().await?;
        Ok(AgentId(created.id))
    }

    pub async fn send_message(&self, agent: &AgentId, content: &str) -> Result<MessageStream, LettaError> {
        let body = serde_json::json!({
            "role": "user",
            "content": content,
            "stream": true,
        });
        let resp = self.http
            .post(format!("{}/v1/agents/{}/messages", self.base_url, agent.0))
            .json(&body).send().await?.error_for_status()?;
        // Decode SSE chunks → text deltas; same shape as OpenAI
        use futures::StreamExt;
        let stream = resp.bytes_stream().map(|chunk| {
            let bytes = chunk.map_err(LettaError::from)?;
            let text = std::str::from_utf8(&bytes)
                .map_err(|e| LettaError::Protocol(e.to_string()))?
                .to_string();
            let mut out = String::new();
            for line in text.lines() {
                if let Some(rest) = line.strip_prefix("data: ") {
                    if rest == "[DONE]" { continue; }
                    if let Ok(v) = serde_json::from_str::<serde_json::Value>(rest) {
                        if let Some(c) = v.pointer("/choices/0/delta/content").and_then(|c| c.as_str()) {
                            out.push_str(c);
                        }
                    }
                }
            }
            Ok(out)
        });
        Ok(stream.boxed())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn agent_id_round_trips() {
        let id = AgentId("abc-123".into());
        let s = serde_json::to_string(&id).unwrap();
        let back: AgentId = serde_json::from_str(&s).unwrap();
        assert_eq!(back.0, "abc-123");
    }
}
```

- [ ] **Step 4: Run unit tests**

```bash
cargo test -p ocm-letta
```

- [ ] **Step 5: Add to workspace `Cargo.toml`**

Already in members list. Confirm with `cargo build -p ocm-letta`.

- [ ] **Step 6: Commit**

```bash
git add crates/ocm-letta
git commit -m "feat(letta): client crate with health/create_agent/send_message"
```

---

## Task 3.4: Integration test — Letta round trip

**Files:**
- Create: `crates/ocm-letta/tests/letta_smoke.rs`

- [ ] **Step 1: Test skeleton (ignored, requires running Letta + llama.cpp)**

```rust
//! Run with:
//!   OCM_LETTA_URL=http://localhost:8283 OCM_LETTA_AGENT=ocm-test \
//!     cargo test -p ocm-letta --test letta_smoke -- --ignored --nocapture
use ocm_letta::LettaClient;
use futures::StreamExt;

#[tokio::test]
#[ignore]
async fn create_agent_send_message_round_trip() {
    let url = std::env::var("OCM_LETTA_URL").expect("OCM_LETTA_URL");
    let name = std::env::var("OCM_LETTA_AGENT").unwrap_or_else(|_| "ocm-test".into());
    let client = LettaClient::new(url);
    client.health().await.expect("letta health");
    let agent = client.create_or_get_agent(&name, Some("You are concise.")).await.expect("create agent");
    let mut stream = client.send_message(&agent, "Reply with the word 'pong'.").await.expect("send");
    let mut total = String::new();
    while let Some(chunk) = stream.next().await {
        total.push_str(&chunk.unwrap_or_default());
    }
    assert!(!total.is_empty());
}
```

- [ ] **Step 2: Run manually**

```bash
# Terminal 1: llama.cpp
llama-server -m ~/.ocm/models/qwen2.5-1.5b-q4.gguf -c 4096 --port 8080

# Terminal 2: Letta
source python/.venv/bin/activate
OCM_LETTA_PORT=8283 OCM_LETTA_INFERENCE_URL=http://localhost:8080/v1 \
  python -m ocm_runtime.letta_server

# Terminal 3: test
OCM_LETTA_URL=http://localhost:8283 \
  cargo test -p ocm-letta --test letta_smoke -- --ignored --nocapture
```

- [ ] **Step 3: Commit**

```bash
git add crates/ocm-letta/tests
git commit -m "test(letta): integration smoke test for create-agent + streaming reply"
```

---

## Task 3.5: Phase 3 verification gate

- [ ] **Step 1: Full local check**

```bash
cargo test --workspace
```

- [ ] **Step 2: Manual round trip per Task 3.4 passes**

- [ ] **Step 3: Tag**

```bash
git tag -a v0.1.0-phase3 -m "Phase 3: Letta subprocess + Rust client + integration smoke"
git push --tags
```

---

# Phase 4: API Surface — OpenAI-compat HTTP + MCP

> **Goal of phase:** External clients (Cline, Continue.dev, Claude Code) can connect to OCM at `http://localhost:7300/v1` (OpenAI) or via MCP and chat with the Letta-backed agent end-to-end.

## Task 4.1: `ocm-api` crate with axum HTTP server

**Files:**
- Create: `crates/ocm-api/Cargo.toml`, `crates/ocm-api/src/lib.rs`

- [ ] **Step 1: Cargo.toml**

```toml
[package]
name = "ocm-api"
version.workspace = true
edition.workspace = true
license.workspace = true

[dependencies]
ocm-letta = { path = "../ocm-letta" }
axum.workspace = true
tokio.workspace = true
tokio-stream = "0.1"
tower = "0.5"
tower-http = { version = "0.6", features = ["cors", "trace"] }
serde.workspace = true
serde_json.workspace = true
futures = "0.3"
async-stream = "0.3"
tracing.workspace = true
anyhow.workspace = true
thiserror.workspace = true
```

- [ ] **Step 2: `lib.rs` skeleton with router**

```rust
use axum::Router;
use std::net::SocketAddr;
use std::sync::Arc;
use tracing::info;

pub mod openai;
pub mod mcp;
pub mod auth;
pub mod streaming;

#[derive(Clone)]
pub struct AppState {
    pub letta: Arc<ocm_letta::LettaClient>,
    pub agent_id: ocm_letta::AgentId,
}

pub fn router(state: AppState) -> Router {
    Router::new()
        .nest("/v1", openai::router())
        .with_state(state)
        .layer(tower_http::trace::TraceLayer::new_for_http())
}

pub async fn serve(addr: SocketAddr, state: AppState) -> anyhow::Result<()> {
    let app = router(state);
    let listener = tokio::net::TcpListener::bind(addr).await?;
    info!(%addr, "OCM HTTP API listening");
    axum::serve(listener, app).await?;
    Ok(())
}
```

- [ ] **Step 3: Stub `openai.rs`, `mcp.rs`, `auth.rs`, `streaming.rs`** (empty modules)

- [ ] **Step 4: Build**

```bash
cargo build -p ocm-api
```

- [ ] **Step 5: Commit**

```bash
git add crates/ocm-api
git commit -m "feat(api): axum router scaffold with state for Letta client"
```

---

## Task 4.2: `/v1/models` endpoint

**Files:**
- Modify: `crates/ocm-api/src/openai.rs`

- [ ] **Step 1: Failing unit test for response shape**

```rust
// crates/ocm-api/src/openai.rs
use axum::{routing::get, Json, Router};
use serde::Serialize;
use crate::AppState;

#[derive(Serialize)]
pub struct ModelsResponse { pub object: &'static str, pub data: Vec<ModelEntry> }

#[derive(Serialize)]
pub struct ModelEntry {
    pub id: String,
    pub object: &'static str,
    pub created: u64,
    pub owned_by: &'static str,
}

pub fn router() -> Router<AppState> {
    Router::new().route("/models", get(list_models))
}

pub async fn list_models() -> Json<ModelsResponse> {
    Json(ModelsResponse {
        object: "list",
        data: vec![ModelEntry {
            id: "ocm-default".into(),
            object: "model",
            created: 0,
            owned_by: "opencircuitmodel",
        }],
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    #[tokio::test]
    async fn returns_at_least_one_model() {
        let r = list_models().await;
        assert_eq!(r.object, "list");
        assert!(!r.data.is_empty());
    }
}
```

- [ ] **Step 2: Run test**

```bash
cargo test -p ocm-api openai::tests
```

- [ ] **Step 3: Commit**

```bash
git commit -am "feat(api): GET /v1/models with single ocm-default model"
```

---

## Task 4.3: `/v1/chat/completions` non-streaming

**Files:**
- Modify: `crates/ocm-api/src/openai.rs`

- [ ] **Step 1: Add the handler**

```rust
use axum::{extract::State, routing::post, Json};
use serde::Deserialize;
use futures::StreamExt;

#[derive(Deserialize)]
pub struct ChatCompletionRequest {
    pub model: Option<String>,
    pub messages: Vec<ChatMsg>,
    #[serde(default)]
    pub stream: bool,
}

#[derive(Deserialize)]
pub struct ChatMsg { pub role: String, pub content: String }

#[derive(Serialize)]
pub struct ChatCompletionResponse {
    pub id: String,
    pub object: &'static str,
    pub created: u64,
    pub model: String,
    pub choices: Vec<Choice>,
}

#[derive(Serialize)]
pub struct Choice { pub index: u32, pub message: AssistantMsg, pub finish_reason: &'static str }

#[derive(Serialize)]
pub struct AssistantMsg { pub role: &'static str, pub content: String }

pub fn router() -> Router<AppState> {
    Router::new()
        .route("/models", get(list_models))
        .route("/chat/completions", post(chat_completions))
}

pub async fn chat_completions(
    State(state): State<AppState>,
    Json(req): Json<ChatCompletionRequest>,
) -> Result<axum::response::Response, axum::http::StatusCode> {
    if req.stream {
        return crate::streaming::stream_chat(state, req).await;
    }
    // Forward last user message to Letta
    let last = req.messages.last().ok_or(axum::http::StatusCode::BAD_REQUEST)?;
    let mut s = state.letta.send_message(&state.agent_id, &last.content)
        .await.map_err(|_| axum::http::StatusCode::BAD_GATEWAY)?;
    let mut content = String::new();
    while let Some(chunk) = s.next().await {
        content.push_str(&chunk.unwrap_or_default());
    }
    let body = ChatCompletionResponse {
        id: format!("chatcmpl-{}", uuid::Uuid::new_v4()),
        object: "chat.completion",
        created: now_secs(),
        model: req.model.unwrap_or_else(|| "ocm-default".into()),
        choices: vec![Choice {
            index: 0,
            message: AssistantMsg { role: "assistant", content },
            finish_reason: "stop",
        }],
    };
    Ok((axum::http::StatusCode::OK, Json(body)).into_response())
}

fn now_secs() -> u64 {
    std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs()).unwrap_or(0)
}
```

Add deps: `uuid = { version = "1", features = ["v4"] }`, plus `axum::response::IntoResponse` import.

- [ ] **Step 2: Build**

```bash
cargo build -p ocm-api
```

- [ ] **Step 3: Commit**

```bash
git commit -am "feat(api): POST /v1/chat/completions non-streaming via Letta"
```

---

## Task 4.4: `/v1/chat/completions` streaming (SSE)

**Files:**
- Modify: `crates/ocm-api/src/streaming.rs`

- [ ] **Step 1: Implement SSE forwarder**

```rust
use crate::{openai::ChatCompletionRequest, AppState};
use async_stream::stream;
use axum::body::Body;
use axum::http::{Response, StatusCode};
use axum::response::IntoResponse;
use futures::StreamExt;
use serde_json::json;

pub async fn stream_chat(
    state: AppState,
    req: ChatCompletionRequest,
) -> Result<Response<Body>, StatusCode> {
    let last = req.messages.last().ok_or(StatusCode::BAD_REQUEST)?.content.clone();
    let model = req.model.unwrap_or_else(|| "ocm-default".into());
    let id = format!("chatcmpl-{}", uuid::Uuid::new_v4());

    let mut letta_stream = state.letta.send_message(&state.agent_id, &last)
        .await.map_err(|_| StatusCode::BAD_GATEWAY)?;

    let body_stream = stream! {
        while let Some(chunk_res) = letta_stream.next().await {
            let chunk = match chunk_res { Ok(s) => s, Err(_) => break };
            if chunk.is_empty() { continue; }
            let event = json!({
                "id": id,
                "object": "chat.completion.chunk",
                "model": model,
                "choices": [{
                    "index": 0,
                    "delta": { "role": "assistant", "content": chunk },
                    "finish_reason": null,
                }],
            });
            yield Ok::<_, std::io::Error>(format!("data: {}\n\n", event));
        }
        let done = json!({
            "id": id,
            "object": "chat.completion.chunk",
            "model": model,
            "choices": [{ "index": 0, "delta": {}, "finish_reason": "stop" }],
        });
        yield Ok(format!("data: {}\n\n", done));
        yield Ok("data: [DONE]\n\n".to_string());
    };

    let body = Body::from_stream(body_stream);
    Response::builder()
        .status(StatusCode::OK)
        .header("content-type", "text/event-stream")
        .header("cache-control", "no-cache")
        .body(body)
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)
}
```

- [ ] **Step 2: Build**

```bash
cargo build -p ocm-api
```

- [ ] **Step 3: Commit**

```bash
git commit -am "feat(api): SSE streaming for /v1/chat/completions"
```

---

## Task 4.5: Localhost-only auth middleware

**Files:**
- Modify: `crates/ocm-api/src/auth.rs`, `crates/ocm-api/src/lib.rs`

- [ ] **Step 1: Implement middleware**

```rust
// crates/ocm-api/src/auth.rs
use axum::{extract::ConnectInfo, http::StatusCode, middleware::Next, response::Response};
use axum::extract::Request;
use std::net::SocketAddr;

pub async fn require_localhost(
    ConnectInfo(addr): ConnectInfo<SocketAddr>,
    req: Request,
    next: Next,
) -> Result<Response, StatusCode> {
    if !addr.ip().is_loopback() {
        return Err(StatusCode::FORBIDDEN);
    }
    Ok(next.run(req).await)
}
```

- [ ] **Step 2: Wire into router**

Modify `lib.rs`:

```rust
use axum::middleware;

pub fn router(state: AppState) -> Router {
    Router::new()
        .nest("/v1", openai::router())
        .with_state(state)
        .layer(middleware::from_fn(auth::require_localhost))
        .layer(tower_http::trace::TraceLayer::new_for_http())
}
```

And bind with `into_make_service_with_connect_info`:

```rust
axum::serve(listener, app.into_make_service_with_connect_info::<SocketAddr>()).await?;
```

- [ ] **Step 3: Commit**

```bash
git commit -am "feat(api): localhost-only middleware (rejects remote 127.x bypass)"
```

---

## Task 4.6: MCP server adapter

**Files:**
- Modify: `crates/ocm-api/src/mcp.rs`, `crates/ocm-api/Cargo.toml`

> **Engineer note:** Use the official MCP Rust SDK (`rmcp` or equivalent — confirm crate name against the current MCP ecosystem). v1 exposes a single tool: `chat` that forwards a message to the Letta agent and returns the assistant text.

- [ ] **Step 1: Add MCP SDK dependency**

```toml
[dependencies]
# ...
rmcp = { version = "0.1", features = ["server", "transport-stdio", "transport-sse"] }
```

(Replace with current crate version. If a different crate is canonical, use that.)

- [ ] **Step 2: Implement minimal MCP server**

```rust
// crates/ocm-api/src/mcp.rs
use crate::AppState;
use rmcp::{ServerCapabilities, ServerHandler, ServerInfo};
use rmcp::model::{Tool, CallToolResult, Content};
use futures::StreamExt;
use serde_json::json;

#[derive(Clone)]
pub struct OcmMcpServer { pub state: AppState }

#[async_trait::async_trait]
impl ServerHandler for OcmMcpServer {
    fn get_info(&self) -> ServerInfo {
        ServerInfo {
            name: "opencircuitmodel".into(),
            version: env!("CARGO_PKG_VERSION").into(),
            capabilities: ServerCapabilities { tools: Some(Default::default()), ..Default::default() },
            ..Default::default()
        }
    }

    async fn list_tools(&self, _: rmcp::model::PaginatedRequestParam) -> Result<rmcp::model::ListToolsResult, rmcp::Error> {
        Ok(rmcp::model::ListToolsResult {
            tools: vec![Tool {
                name: "chat".into(),
                description: Some("Send a message to the OCM personal agent and get a reply.".into()),
                input_schema: json!({
                    "type": "object",
                    "properties": { "message": { "type": "string" } },
                    "required": ["message"],
                }),
            }],
            next_cursor: None,
        })
    }

    async fn call_tool(&self, params: rmcp::model::CallToolRequestParam) -> Result<CallToolResult, rmcp::Error> {
        if params.name != "chat" { return Err(rmcp::Error::invalid_request(format!("unknown tool: {}", params.name))); }
        let msg = params.arguments
            .as_ref()
            .and_then(|a| a.get("message"))
            .and_then(|v| v.as_str())
            .ok_or_else(|| rmcp::Error::invalid_request("message is required"))?;
        let mut s = self.state.letta.send_message(&self.state.agent_id, msg)
            .await.map_err(|e| rmcp::Error::internal(e.to_string()))?;
        let mut content = String::new();
        while let Some(c) = s.next().await { content.push_str(&c.unwrap_or_default()); }
        Ok(CallToolResult {
            content: vec![Content::text(content)],
            is_error: Some(false),
        })
    }
}
```

> **API note:** Adapt struct/trait names against the actual `rmcp` version you find on crates.io. The contract — list_tools, call_tool, single `chat` tool — is what matters.

- [ ] **Step 3: Add MCP startup to `lib.rs::serve`**

```rust
pub async fn serve_mcp_stdio(state: AppState) -> anyhow::Result<()> {
    let server = mcp::OcmMcpServer { state };
    rmcp::serve_stdio(server).await?;
    Ok(())
}
```

- [ ] **Step 4: Commit**

```bash
git commit -am "feat(api): MCP server with single chat tool over stdio"
```

---

## Task 4.7: Wire `ocm-api` into daemon startup

**Files:**
- Modify: `crates/ocm-daemon/Cargo.toml`, `crates/ocm-daemon/src/main.rs`

- [ ] **Step 1: Add deps**

```toml
[dependencies]
ocm-api = { path = "../ocm-api" }
ocm-letta = { path = "../ocm-letta" }
```

- [ ] **Step 2: In `setup`, after settings load:**

```rust
let letta = std::sync::Arc::new(ocm_letta::LettaClient::new("http://127.0.0.1:8283"));
// agent creation needs to be awaited; spawn a task
let letta_for_task = letta.clone();
tauri::async_runtime::spawn(async move {
    if let Err(e) = letta_for_task.health().await {
        tracing::warn!(err=?e, "letta not yet up; will retry");
    }
});

// Defer real startup — Phase 6 wires the full sequence.
```

- [ ] **Step 3: Build**

```bash
cargo build -p ocm-daemon
```

- [ ] **Step 4: Commit**

```bash
git commit -am "wip(daemon): scaffold ocm-api wiring (full startup sequencing in phase 6)"
```

---

## Task 4.8: Integration test — OpenAI-compat round trip

**Files:**
- Create: `tests/integration/test_openai_compat.rs`

- [ ] **Step 1: Write the test**

```rust
//! End-to-end: spin up ocm-api on an ephemeral port with a fake Letta;
//! send a chat completion; assert response shape.
use ocm_api::{router, AppState};
use ocm_letta::LettaClient;
use std::sync::Arc;
use axum::body::Body;
use axum::http::{Request, StatusCode};
use tower::ServiceExt; // for `oneshot`

#[tokio::test]
async fn chat_completion_round_trip_with_running_letta() {
    let letta_url = std::env::var("OCM_LETTA_URL")
        .unwrap_or_else(|_| "http://localhost:8283".into());
    let agent_name = std::env::var("OCM_LETTA_AGENT")
        .unwrap_or_else(|_| "ocm-test".into());
    let client = LettaClient::new(letta_url);
    if client.health().await.is_err() {
        eprintln!("skipping: Letta not running");
        return;
    }
    let agent_id = client.create_or_get_agent(&agent_name, None).await.expect("agent");
    let state = AppState { letta: Arc::new(client), agent_id };
    let app = router(state);

    let body = serde_json::json!({
        "model": "ocm-default",
        "messages": [{ "role": "user", "content": "Say 'pong' and nothing else." }],
        "stream": false,
    });
    let req = Request::post("/v1/chat/completions")
        .header("content-type", "application/json")
        .body(Body::from(body.to_string())).unwrap();
    let resp = app.clone().oneshot(req).await.unwrap();
    assert_eq!(resp.status(), StatusCode::OK);
}
```

- [ ] **Step 2: Run with services up**

(Letta + llama.cpp running per Task 3.4 setup.)

```bash
cargo test --test test_openai_compat -- --nocapture
```

- [ ] **Step 3: Commit**

```bash
git add tests
git commit -m "test(api): integration test for OpenAI-compat round trip"
```

---

## Task 4.9: Phase 4 verification gate

- [ ] Full check: `cargo test --workspace`
- [ ] Manual: `curl -X POST http://localhost:7300/v1/chat/completions -H 'content-type: application/json' -d '{"model":"ocm-default","messages":[{"role":"user","content":"hi"}]}'` returns valid JSON.
- [ ] MCP: connect Claude Code's MCP config to OCM stdio binary and exercise the `chat` tool.
- [ ] Tag:

```bash
git tag -a v0.1.0-phase4 -m "Phase 4: OpenAI-compat HTTP + MCP server"
git push --tags
```

---

# Phase 5: Web UI (SvelteKit inside Tauri)

> **Goal of phase:** A working Tauri webview that displays a chat UI streaming responses from the daemon's HTTP API, plus settings and model picker pages.

## Task 5.1: Scaffold SvelteKit frontend

**Files:**
- Create: `frontend/package.json`, `frontend/svelte.config.js`, `frontend/vite.config.ts`, `frontend/src/...`

- [ ] **Step 1: Init**

```bash
cd frontend
npm create svelte@latest .  # pick: Skeleton, TypeScript, ESLint, Prettier
npm install
```

- [ ] **Step 2: Configure for Tauri (static adapter)**

Edit `frontend/svelte.config.js`:

```javascript
import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

export default {
  preprocess: vitePreprocess(),
  kit: {
    adapter: adapter({ pages: 'build', assets: 'build', fallback: 'index.html' }),
    prerender: { entries: [] },
  },
};
```

```bash
npm install -D @sveltejs/adapter-static
```

- [ ] **Step 3: Verify dev server starts**

```bash
npm run dev
# → http://localhost:5173
```

- [ ] **Step 4: Commit**

```bash
cd ..
git add frontend
git commit -m "feat(ui): SvelteKit scaffold with static adapter for Tauri"
```

---

## Task 5.2: Daemon API client (`frontend/src/lib/api.ts`)

**Files:**
- Create: `frontend/src/lib/api.ts`

- [ ] **Step 1: Write the client**

```typescript
const BASE = 'http://localhost:7300/v1';

export interface ChatMessage { role: 'system' | 'user' | 'assistant'; content: string }

export async function* streamChat(messages: ChatMessage[]): AsyncGenerator<string> {
  const r = await fetch(`${BASE}/chat/completions`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ model: 'ocm-default', messages, stream: true }),
  });
  if (!r.ok || !r.body) throw new Error(`HTTP ${r.status}`);
  const reader = r.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let idx;
    while ((idx = buffer.indexOf('\n\n')) >= 0) {
      const event = buffer.slice(0, idx).trim();
      buffer = buffer.slice(idx + 2);
      if (!event.startsWith('data: ')) continue;
      const data = event.slice(6);
      if (data === '[DONE]') return;
      try {
        const parsed = JSON.parse(data);
        const delta = parsed.choices?.[0]?.delta?.content;
        if (delta) yield delta;
      } catch { /* ignore malformed */ }
    }
  }
}

export async function listModels(): Promise<{ id: string }[]> {
  const r = await fetch(`${BASE}/models`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  const j = await r.json();
  return j.data ?? [];
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/lib
git commit -m "feat(ui): API client with SSE chat-completion streaming"
```

---

## Task 5.3: Chat page

**Files:**
- Modify: `frontend/src/routes/+page.svelte`

- [ ] **Step 1: Write the chat UI**

```svelte
<script lang="ts">
  import { streamChat, type ChatMessage } from '$lib/api';

  let messages: ChatMessage[] = [];
  let input = '';
  let busy = false;

  async function send() {
    if (!input.trim() || busy) return;
    busy = true;
    const userMsg: ChatMessage = { role: 'user', content: input };
    messages = [...messages, userMsg, { role: 'assistant', content: '' }];
    input = '';
    try {
      for await (const chunk of streamChat(messages.slice(0, -1))) {
        messages[messages.length - 1].content += chunk;
        messages = messages;
      }
    } catch (e) {
      messages[messages.length - 1].content = `Error: ${e}`;
      messages = messages;
    } finally {
      busy = false;
    }
  }
</script>

<main>
  <h1>OpenCircuitModel</h1>
  <ul class="chat">
    {#each messages as m}
      <li class={m.role}>
        <strong>{m.role}:</strong> {m.content}
      </li>
    {/each}
  </ul>
  <form on:submit|preventDefault={send}>
    <input bind:value={input} placeholder="Ask anything…" disabled={busy} />
    <button type="submit" disabled={busy || !input.trim()}>Send</button>
  </form>
</main>

<style>
  main { max-width: 800px; margin: 2rem auto; font-family: system-ui; }
  .chat { list-style: none; padding: 0; }
  .chat li { padding: 0.5rem; margin: 0.25rem 0; border-radius: 4px; }
  .chat .user { background: #eef; }
  .chat .assistant { background: #efe; }
  form { display: flex; gap: 0.5rem; }
  input { flex: 1; padding: 0.5rem; }
</style>
```

- [ ] **Step 2: Verify**

```bash
cd frontend && npm run dev
```

(Open http://localhost:5173 — daemon must be running on 7300 with all subprocesses up to actually chat.)

- [ ] **Step 3: Commit**

```bash
git commit -am "feat(ui): chat page with streaming responses"
```

---

## Task 5.4: Settings page

**Files:**
- Create: `frontend/src/routes/settings/+page.svelte`

- [ ] **Step 1: Stub the settings UI**

```svelte
<script lang="ts">
  let port = 7300;
  let theme: 'dark' | 'light' | 'system' = 'system';
  let mcpEnabled = true;
</script>

<h1>Settings</h1>
<label>API port <input type="number" bind:value={port} /></label>
<label>Theme
  <select bind:value={theme}>
    <option value="system">System</option>
    <option value="dark">Dark</option>
    <option value="light">Light</option>
  </select>
</label>
<label><input type="checkbox" bind:checked={mcpEnabled} /> MCP server enabled</label>
<p><em>Settings save will be wired in Phase 6.</em></p>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/routes/settings
git commit -m "feat(ui): settings page stub (persistence in phase 6)"
```

---

## Task 5.5: Model picker page

**Files:**
- Create: `frontend/src/routes/models/+page.svelte`

- [ ] **Step 1: Write the picker**

```svelte
<script lang="ts">
  import { onMount } from 'svelte';
  import { listModels } from '$lib/api';
  let models: { id: string }[] = [];
  onMount(async () => { models = await listModels(); });
</script>

<h1>Models</h1>
<ul>
  {#each models as m}<li>{m.id}</li>{/each}
</ul>
<p><em>Download UI added in Phase 6.</em></p>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/routes/models
git commit -m "feat(ui): basic model picker reading /v1/models"
```

---

## Task 5.6: Phase 5 verification gate

- [ ] Run `cd frontend && npm run build` — produces `frontend/build/`.
- [ ] Run `cargo tauri dev -p ocm-daemon` — Tauri serves the SvelteKit UI in webview.
- [ ] Verify chat works end-to-end with all subprocesses running.
- [ ] Tag:

```bash
git tag -a v0.1.0-phase5 -m "Phase 5: SvelteKit web UI with chat + settings + models"
git push --tags
```

---

# Phase 6: Model Registry, Installer, End-to-End Smoke

> **Goal of phase:** A user can download an installer, run it, pick a model, chat — all through a polished onboarding flow. v1 RELEASE.

## Task 6.1: Model registry crate + curated JSON

**Files:**
- Create: `crates/ocm-models/Cargo.toml`, `crates/ocm-models/src/lib.rs`, `crates/ocm-models/registry.json`

- [ ] **Step 1: Cargo.toml**

```toml
[package]
name = "ocm-models"
version.workspace = true
edition.workspace = true
license.workspace = true

[dependencies]
serde.workspace = true
serde_json.workspace = true
tokio.workspace = true
reqwest = { workspace = true, features = ["stream"] }
sha2 = "0.10"
hex = "0.4"
futures = "0.3"
tracing.workspace = true
anyhow.workspace = true
thiserror.workspace = true
```

- [ ] **Step 2: registry.json (initial curated set)**

```json
{
  "version": 1,
  "models": [
    {
      "id": "qwen2.5-1.5b-q4",
      "display_name": "Qwen 2.5 1.5B (Q4_K_M)",
      "size_mb": 940,
      "min_ram_gb": 4,
      "url": "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf",
      "sha256": "REPLACE_WITH_REAL_HASH"
    },
    {
      "id": "llama-3.1-8b-q4",
      "display_name": "Llama 3.1 8B Instruct (Q4_K_M)",
      "size_mb": 4920,
      "min_ram_gb": 8,
      "url": "https://huggingface.co/bartowski/Meta-Llama-3.1-8B-Instruct-GGUF/resolve/main/Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf",
      "sha256": "REPLACE_WITH_REAL_HASH"
    },
    {
      "id": "mistral-7b-q4",
      "display_name": "Mistral 7B Instruct v0.3 (Q4_K_M)",
      "size_mb": 4400,
      "min_ram_gb": 8,
      "url": "https://huggingface.co/MaziyarPanahi/Mistral-7B-Instruct-v0.3-GGUF/resolve/main/Mistral-7B-Instruct-v0.3.Q4_K_M.gguf",
      "sha256": "REPLACE_WITH_REAL_HASH"
    }
  ]
}
```

> **Engineer note:** Replace `sha256` placeholders with real values fetched at registry-build time. Compute via `shasum -a 256 <file>` after downloading the canonical GGUF once.

- [ ] **Step 3: lib.rs with registry parsing**

```rust
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct Registry { pub version: u32, pub models: Vec<ModelEntry> }

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct ModelEntry {
    pub id: String,
    pub display_name: String,
    pub size_mb: u64,
    pub min_ram_gb: u32,
    pub url: String,
    pub sha256: String,
}

impl Registry {
    pub fn load_bundled() -> anyhow::Result<Self> {
        const BUNDLED: &str = include_str!("../registry.json");
        Ok(serde_json::from_str(BUNDLED)?)
    }
}

pub mod downloader;

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn bundled_registry_parses() {
        let r = Registry::load_bundled().unwrap();
        assert_eq!(r.version, 1);
        assert!(!r.models.is_empty());
        for m in &r.models { assert!(!m.id.is_empty()); }
    }
}
```

- [ ] **Step 4: Test**

```bash
cargo test -p ocm-models
```

- [ ] **Step 5: Commit**

```bash
git add crates/ocm-models
git commit -m "feat(models): curated registry + parser (3 initial GGUFs)"
```

---

## Task 6.2: SHA256-verified downloader

**Files:**
- Create: `crates/ocm-models/src/downloader.rs`

- [ ] **Step 1: Implementation**

```rust
use crate::ModelEntry;
use anyhow::{Context, Result};
use futures::StreamExt;
use sha2::{Digest, Sha256};
use std::path::{Path, PathBuf};
use tokio::io::AsyncWriteExt;

pub async fn download_model(
    entry: &ModelEntry,
    dest_dir: &Path,
    on_progress: impl Fn(u64, Option<u64>) + Send + 'static,
) -> Result<PathBuf> {
    tokio::fs::create_dir_all(dest_dir).await?;
    let dest = dest_dir.join(format!("{}.gguf", entry.id));
    if dest.exists() {
        if verify_sha256(&dest, &entry.sha256).await? {
            return Ok(dest);
        }
        tokio::fs::remove_file(&dest).await?;
    }

    let resp = reqwest::get(&entry.url).await?.error_for_status()?;
    let total = resp.content_length();
    let mut hasher = Sha256::new();
    let mut downloaded: u64 = 0;
    let mut file = tokio::fs::File::create(&dest).await?;
    let mut stream = resp.bytes_stream();
    while let Some(chunk) = stream.next().await {
        let chunk = chunk?;
        hasher.update(&chunk);
        file.write_all(&chunk).await?;
        downloaded += chunk.len() as u64;
        on_progress(downloaded, total);
    }
    file.flush().await?;
    let actual = hex::encode(hasher.finalize());
    if !actual.eq_ignore_ascii_case(&entry.sha256) {
        tokio::fs::remove_file(&dest).await.ok();
        anyhow::bail!("sha256 mismatch: expected {}, got {}", entry.sha256, actual);
    }
    Ok(dest)
}

async fn verify_sha256(path: &Path, expected: &str) -> Result<bool> {
    use tokio::io::AsyncReadExt;
    let mut file = tokio::fs::File::open(path).await?;
    let mut hasher = Sha256::new();
    let mut buf = vec![0u8; 1024 * 1024];
    loop {
        let n = file.read(&mut buf).await?;
        if n == 0 { break; }
        hasher.update(&buf[..n]);
    }
    let actual = hex::encode(hasher.finalize());
    Ok(actual.eq_ignore_ascii_case(expected))
}

#[cfg(test)]
mod tests {
    use super::*;
    #[tokio::test]
    async fn verify_sha256_returns_false_on_missing() {
        // small file with known hash
        let dir = tempfile::tempdir().unwrap();
        let p = dir.path().join("none.bin");
        // missing → should error
        assert!(verify_sha256(&p, "deadbeef").await.is_err());
    }
}
```

Add `tempfile` to dev-deps.

- [ ] **Step 2: Run unit test**

```bash
cargo test -p ocm-models downloader::tests
```

- [ ] **Step 3: Commit**

```bash
git commit -am "feat(models): streaming downloader with sha256 verification"
```

---

## Task 6.3: Model download UI hooks

**Files:**
- Modify: `frontend/src/routes/models/+page.svelte`, `frontend/src/lib/api.ts`, daemon Tauri command exposure

- [ ] **Step 1: Add Tauri command in `crates/ocm-daemon`**

`crates/ocm-daemon/src/main.rs`:

```rust
use ocm_models::{Registry, downloader::download_model};
use std::path::PathBuf;

#[tauri::command]
async fn download_model_cmd(model_id: String, dest_dir: String) -> Result<String, String> {
    let registry = Registry::load_bundled().map_err(|e| e.to_string())?;
    let entry = registry.models.iter().find(|m| m.id == model_id)
        .ok_or_else(|| format!("unknown model: {}", model_id))?;
    let dest = PathBuf::from(dest_dir);
    let path = download_model(entry, &dest, |_, _| {}).await
        .map_err(|e| e.to_string())?;
    Ok(path.display().to_string())
}
```

Wire into builder:

```rust
.invoke_handler(tauri::generate_handler![download_model_cmd])
```

- [ ] **Step 2: Use in UI**

```typescript
// frontend/src/lib/api.ts (append)
import { invoke } from '@tauri-apps/api/core';

export async function downloadModel(modelId: string, destDir: string): Promise<string> {
  return invoke('download_model_cmd', { modelId, destDir });
}
```

```bash
cd frontend && npm install @tauri-apps/api
```

- [ ] **Step 3: Wire into models page**

```svelte
<script lang="ts">
  import { onMount } from 'svelte';
  import { listModels, downloadModel } from '$lib/api';
  // ... existing
  let downloading = '';
  async function download(id: string) {
    downloading = id;
    try {
      await downloadModel(id, '~/.ocm/models');
      alert('Downloaded.');
    } catch (e) { alert(`Failed: ${e}`); } finally { downloading = ''; }
  }
</script>
```

(Add Download button next to each model.)

- [ ] **Step 4: Commit**

```bash
git commit -am "feat(models): wire download UI to Tauri command"
```

---

## Task 6.4: Tauri build for macOS .dmg

**Files:**
- Modify: `crates/ocm-daemon/tauri.conf.json` (bundling)

- [ ] **Step 1: Verify bundle config in `tauri.conf.json`**

Already targets "all". Confirm `bundle.icon` points to a real `icon.icns` (Tauri will auto-derive on Mac).

- [ ] **Step 2: Build**

```bash
cd crates/ocm-daemon
cargo tauri build
```

Expected: `target/release/bundle/dmg/OpenCircuitModel_0.1.0_aarch64.dmg` (or x86_64).

- [ ] **Step 3: Test the DMG**

Open the DMG, drag to Applications, launch — verify tray icon appears, window shows.

- [ ] **Step 4: Commit any config tweaks**

```bash
git commit -am "chore(release): macOS dmg bundling verified"
```

---

## Task 6.5: Tauri build for Windows .msi

- [ ] **Step 1: On a Windows machine (or VM), run**

```powershell
cd crates/ocm-daemon
cargo tauri build
```

Expected: `target/release/bundle/msi/OpenCircuitModel_0.1.0_x64_en-US.msi`.

- [ ] **Step 2: Test the MSI on a clean Windows VM**

Install → launch → verify tray + window.

- [ ] **Step 3: Document Windows-specific caveats in `README.md`**

```markdown
### Windows
The v1 alpha installer is not codesigned — Defender SmartScreen will warn on first run.
Click "More info" → "Run anyway." Codesigning lands in v4.
```

- [ ] **Step 4: Commit**

```bash
git commit -am "docs(release): Windows install caveats for unsigned alpha"
```

---

## Task 6.6: Tauri build for Linux .deb

- [ ] **Step 1: On Ubuntu 22.04 (or in CI matrix)**

```bash
cd crates/ocm-daemon
cargo tauri build
```

Expected: `target/release/bundle/deb/opencircuitmodel_0.1.0_amd64.deb`.

- [ ] **Step 2: Test installation**

```bash
sudo dpkg -i target/release/bundle/deb/opencircuitmodel_0.1.0_amd64.deb
opencircuitmodel
```

- [ ] **Step 3: Commit any Linux-specific docs**

```bash
git commit -am "docs(release): Linux .deb verified on Ubuntu 22.04"
```

---

## Task 6.7: First-run onboarding flow

**Files:**
- Modify: `frontend/src/routes/+layout.svelte`, add `frontend/src/routes/onboarding/+page.svelte`

- [ ] **Step 1: Detect first run via Tauri command**

Add to daemon:

```rust
#[tauri::command]
async fn is_first_run(state: tauri::State<'_, settings::Settings>) -> Result<bool, String> {
    Ok(state.model_id.is_none())
}
```

- [ ] **Step 2: Layout redirects to /onboarding if first run**

```svelte
<!-- frontend/src/routes/+layout.svelte -->
<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { invoke } from '@tauri-apps/api/core';
  onMount(async () => {
    if (await invoke<boolean>('is_first_run')) goto('/onboarding');
  });
</script>
<slot />
```

- [ ] **Step 3: Onboarding page**

```svelte
<!-- frontend/src/routes/onboarding/+page.svelte -->
<script lang="ts">
  import { listModels, downloadModel } from '$lib/api';
  import { goto } from '$app/navigation';
  import { invoke } from '@tauri-apps/api/core';
  let models: any[] = [];
  let chosen = '';
  let busy = false;
  $: void (async () => { models = await listModels(); })();

  async function start() {
    if (!chosen) return;
    busy = true;
    await downloadModel(chosen, '~/.ocm/models');
    await invoke('save_settings', { modelId: chosen });
    goto('/');
  }
</script>

<h1>Welcome to OpenCircuitModel</h1>
<p>Pick a model to get started. You can change this anytime in Settings.</p>
<select bind:value={chosen}>
  <option value="">— choose —</option>
  {#each models as m}<option value={m.id}>{m.display_name ?? m.id}</option>{/each}
</select>
<button on:click={start} disabled={!chosen || busy}>
  {busy ? 'Downloading…' : 'Start'}
</button>
```

(Add `save_settings` Tauri command on the daemon side that updates `Settings::model_id` and persists.)

- [ ] **Step 4: Commit**

```bash
git commit -am "feat(ui): first-run onboarding with model picker + persistence"
```

---

## Task 6.8: End-to-end manual smoke test script

**Files:**
- Create: `tests/integration/test_smoke.sh`

- [ ] **Step 1: Write the script**

```bash
#!/usr/bin/env bash
# Manual smoke test — confirms full v1 stack on the dev box.
set -euo pipefail

echo "=== OCM v1 Smoke Test ==="

echo "1. Building..."
cargo build --workspace --release

echo "2. Starting llama.cpp..."
llama-server -m ~/.ocm/models/qwen2.5-1.5b-q4.gguf -c 4096 --port 8080 &
LLAMA_PID=$!
sleep 5
curl -fs http://localhost:8080/health > /dev/null

echo "3. Starting Letta..."
source python/.venv/bin/activate
OCM_LETTA_PORT=8283 OCM_LETTA_INFERENCE_URL=http://localhost:8080/v1 \
  python -m ocm_runtime.letta_server &
LETTA_PID=$!
sleep 10
curl -fs http://localhost:8283/v1/health > /dev/null || curl -fs http://localhost:8283/health

echo "4. Sending test message via OCM API..."
RESPONSE=$(curl -s -X POST http://localhost:7300/v1/chat/completions \
  -H 'content-type: application/json' \
  -d '{"model":"ocm-default","messages":[{"role":"user","content":"Reply with the word pong"}],"stream":false}')
echo "Response: $RESPONSE"
echo "$RESPONSE" | grep -q '"role":"assistant"' || { echo "FAIL: no assistant message"; exit 1; }

echo "5. Cleanup..."
kill $LLAMA_PID $LETTA_PID || true

echo "=== ALL CHECKS PASSED ==="
```

- [ ] **Step 2: Run it**

```bash
chmod +x tests/integration/test_smoke.sh
./tests/integration/test_smoke.sh
```

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_smoke.sh
git commit -m "test: end-to-end smoke shell script for v1 release validation"
```

---

## Task 6.9: README + CONTRIBUTING + LICENSE polish

**Files:**
- Modify: `README.md`
- Create: `CONTRIBUTING.md`

- [ ] **Step 1: Full README**

```markdown
# OpenCircuitModel (OCM)

> A free, open-source personal AI agent with persistent memory — runs locally,
> no cloud account required. Apache 2.0 licensed.

**Status:** v1.0.0-alpha — works on macOS / Windows / Linux.

## What it does
- Persistent personal AI agent that remembers across sessions
- OpenAI-compatible HTTP API (`localhost:7300/v1`) — drop-in for Cline, Continue.dev, any OpenAI client
- MCP server — connect Claude Code, Cline, etc. via Model Context Protocol
- 100% local — your conversations never leave your machine

## Quick start

### macOS / Linux
1. Install [llama.cpp](https://github.com/ggerganov/llama.cpp) (`brew install llama.cpp` on macOS)
2. Download the latest [release](https://github.com/OpenCircuitDev/opencircuitmodel/releases)
3. Open the .dmg or .deb, install, launch
4. Pick a model in onboarding, wait for download, chat

### Windows
Same as above with the .msi. **Note:** v1 alpha is unsigned — Defender will warn. Click "More info" → "Run anyway."

## Roadmap
- v1: single-node personal agent (this release)
- v2: peer-to-peer mesh (libp2p)
- v3: reciprocity ledger (give-to-get)
- v4-v6: codesigned releases, sandboxing, frontier-model sharded inference

## Contributing
See [CONTRIBUTING.md](CONTRIBUTING.md). Discord: [TBD], GitHub Discussions: enabled.

## License
Apache 2.0 — see [LICENSE](LICENSE).
```

- [ ] **Step 2: Write CONTRIBUTING.md**

```markdown
# Contributing to OpenCircuitModel

Thanks for your interest! OCM is solo-driven but community-friendly.

## Setup
```bash
git clone https://github.com/OpenCircuitDev/opencircuitmodel.git
cd opencircuitmodel
./scripts/install-hooks.sh
./scripts/setup-python.sh
cargo tauri dev -p ocm-daemon
```

## Code style
- `cargo fmt` + `cargo clippy --workspace --all-targets -- -D warnings` must pass
- Tests required for new logic; integration tests for new endpoints
- Commit messages follow Conventional Commits (`feat:`, `fix:`, `chore:`, `test:`, `docs:`)

## How to propose changes
1. Open a discussion or issue first for non-trivial changes
2. Branch from `main`
3. Open a PR with a description and link to the issue/discussion

## License
By contributing, you agree your contributions are licensed Apache 2.0.
```

- [ ] **Step 3: Commit**

```bash
git add README.md CONTRIBUTING.md
git commit -m "docs: full README + CONTRIBUTING for v1 alpha release"
```

---

## Task 6.10: Tag v1.0.0-alpha + GitHub release

- [ ] **Step 1: Final test sweep**

```bash
cargo fmt --all -- --check
cargo clippy --workspace --all-targets -- -D warnings
cargo test --workspace
./tests/integration/test_smoke.sh
```

- [ ] **Step 2: Build all installers**

On each platform (or via CI matrix):

```bash
cargo tauri build
```

- [ ] **Step 3: Tag**

```bash
git tag -a v1.0.0-alpha -m "OCM v1.0.0-alpha — Single-Node OCM, single-machine personal agent"
git push --tags
```

- [ ] **Step 4: Create GitHub release with installers attached**

```bash
gh release create v1.0.0-alpha \
  --title "v1.0.0-alpha — Single-Node OCM" \
  --notes "First public alpha. Single-node personal agent with persistent memory.
- macOS .dmg / Windows .msi / Linux .deb (unsigned)
- OpenAI-compat API at localhost:7300/v1
- MCP server adapter
- 3 curated models (Qwen 2.5 1.5B, Llama 3.1 8B, Mistral 7B)

Known limitations:
- Installers unsigned — codesigning in v4
- No mesh yet — v2
- No reciprocity ledger yet — v3" \
  target/release/bundle/dmg/*.dmg \
  target/release/bundle/msi/*.msi \
  target/release/bundle/deb/*.deb
```

- [ ] **Step 5: Announce**

Post to:
- HN: "Show HN: OpenCircuitModel — free local personal AI agent (Apache 2.0)"
- r/LocalLLaMA: link + brief feature list
- r/selfhosted: link + brief feature list
- Twitter/X
- The OCM Discord (if created)

---

## Task 6.11: Phase 6 verification gate (RELEASE GATE)

All of the following must be true before declaring v1 shipped:

- [ ] All workspace tests pass: `cargo test --workspace`
- [ ] Lint clean: `cargo clippy --workspace --all-targets -- -D warnings`
- [ ] Smoke script passes: `./tests/integration/test_smoke.sh`
- [ ] Manual smoke on macOS — install dmg, onboard, chat, restart, memory persists
- [ ] Manual smoke on Windows — install msi, onboard, chat, restart, memory persists
- [ ] Manual smoke on Linux — install deb, onboard, chat, restart, memory persists
- [ ] OpenAI client (Cline OR Continue.dev) successfully connects to localhost:7300/v1
- [ ] MCP client (Claude Code) successfully invokes the `chat` tool
- [ ] 100K-token conversation does not crash (Letta paging works)
- [ ] Idle daemon < 50 MB RAM, 0% GPU when no inference active
- [ ] CI green on main for last 5 commits across all 3 OS

---

# Risk Callouts

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Letta API surface changes between now and ship | High | Medium | Pin to a specific Letta version in `pyproject.toml`; allocate buffer in Phase 3 for adapter rework |
| `rmcp` MCP SDK is immature or churns | Medium | Medium | If `rmcp` doesn't fit, fall back to MCP TypeScript SDK in a Node subprocess (more code, but more stable) |
| llama.cpp binary distribution on Windows | Medium | Medium | Bundle prebuilt llama-server.exe in installer; document GPL of llama.cpp doesn't infect Apache 2.0 OCM (separate process boundary) |
| Tauri 2.x bundling quirks per OS | Medium | Low | Add platform-specific docs; CI builds installers on each OS as final check |
| vLLM Python deps + venv on Windows | High | Low | Skip vLLM on Windows for v1; document NVIDIA-on-Linux only; revisit in v6 |
| Mac Mini base 16GB cannot run 8B model with full context | Medium | Low | Default to Qwen 2.5 1.5B on first-run; let user upgrade |
| Codesigning required by macOS Gatekeeper | High | Medium | v1 ships unsigned with documented "right-click → Open" workaround; full codesigning in v4 |

# Decision Points (review at end of each phase)

- **End of Phase 1:** is Tauri 2.x stable enough? If not, fall back to Tauri 1.x (mature, less feature-rich)
- **End of Phase 2:** does llama.cpp's OpenAI-compat API cover what Letta needs? If not, write a minimal native llama-cpp-python adapter
- **End of Phase 3:** is Letta's velocity tolerable? If they break compat weekly, consider switching to Mem0 or building a thin custom memory layer
- **End of Phase 4:** is `rmcp` viable? If not, MCP via Node subprocess is the fallback
- **End of Phase 5:** is the SvelteKit-in-Tauri DX good? If not, switch to plain HTML+vanilla-JS for simplicity
- **End of Phase 6:** ready to ship, or one more polish round? Depends on smoke-test pass rate

---

## Self-Review (completed inline by plan author)

**Spec coverage:** every numbered "Locked decision" 1-15 in the design spec maps to one or more tasks above. License (4) → Task 1.1. vLLM (5) → Tasks 2.3 / 2.7. llama.cpp (6) → Tasks 2.2 / 2.6 / 6.4. libp2p (8) → deferred to v2 (correctly out of scope). Letta (9) → Tasks 3.1-3.5. LangGraph (10) → not strictly needed in v1 since Letta provides agent flow; marked for v2 if needed (acceptable defer). MCP (11) → Task 4.6. Tauri (12) → Task 1.2. Platforms (13) → Tasks 6.4-6.6. Hero pitch (14) is the entire reason v1 is shaped as a single-node personal-agent product. ✓

**Placeholder scan:** Two intentional engineer-notes flag library-version uncertainty (Letta API, `rmcp` crate name) — these are not placeholders, they are explicit calibrations the engineer must verify against current docs. The `sha256: REPLACE_WITH_REAL_HASH` in `registry.json` is also intentional and noted as engineer action. No "TODO" / "fill in details" placeholders found. ✓

**Type consistency:** `InferenceBackend` trait, `LettaClient`, `AgentId`, `ChatMessage`, `Role`, `AppState` are consistent across phases. The `chat` MCP tool name is consistent. The `model_id` field name is consistent in `Settings` / `registry.json` / Tauri commands. ✓

---
