//! Daemon startup orchestration — wires inference backend + memory client
//! + API server into a coherent boot sequence.
//!
//! Called from Tauri's setup() closure as a background tokio task. The OCM
//! daemon is *resilient by design*: if external dependencies (Mem0 server,
//! llama.cpp / vLLM) aren't running, the daemon stays up with degraded
//! functionality and logs warnings. The user gets a Tauri tray + window
//! that reports status; chat requests fail with clear errors.

use crate::settings::{Backend, Settings};
use crate::supervisor::{self, Supervisor, SupervisorPolicy, SupervisorStatus};
use ocm_inference::ollama::DEFAULT_MODEL as DEFAULT_OLLAMA_MODEL;
use ocm_inference::selector::{self, BackendKind, DEFAULT_OLLAMA_BASE_URL};
use std::net::{IpAddr, Ipv4Addr, SocketAddr};
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};
use std::time::Duration;
use tracing::{info, warn};

/// Default base URL for the local inference backend (llama.cpp/vLLM).
/// vLLM defaults to 8000; llama.cpp's llama-server defaults to 8080. We pick
/// 8080 by default since llama.cpp is the default Mac/CPU backend; users with
/// vLLM can override via settings.
pub const DEFAULT_INFERENCE_BASE_URL: &str = "http://127.0.0.1:8080";

/// Default base URL for Mem0 OpenMemory MCP. Mem0's docker-compose defaults
/// to 8765 for the local server.
pub const DEFAULT_MEM0_BASE_URL: &str = "http://127.0.0.1:8765";

/// Number of memories to retrieve per chat turn (library-driven retrieval
/// per spec row 9). Conservative default — users can override via settings.
pub const DEFAULT_RETRIEVAL_TOP_K: u32 = 5;

/// Soft-attempt to verify external services are reachable. Returns Ok even
/// when they aren't — the daemon's job is to stay up and report status, not
/// to refuse to launch.
pub async fn probe_dependencies(inference_url: &str, mem0_url: &str) -> DependencyStatus {
    let inference_ok =
        probe_url(inference_url, "/v1/models").await || probe_url(inference_url, "/health").await;
    let mem0_ok = probe_url(mem0_url, "/v1/health").await || probe_url(mem0_url, "/health").await;

    DependencyStatus {
        inference_reachable: inference_ok,
        memory_reachable: mem0_ok,
    }
}

#[derive(Debug, Clone, Copy)]
pub struct DependencyStatus {
    pub inference_reachable: bool,
    pub memory_reachable: bool,
}

async fn probe_url(base: &str, path: &str) -> bool {
    let url = format!("{base}{path}");
    let client = match reqwest::Client::builder()
        .timeout(Duration::from_millis(1500))
        .build()
    {
        Ok(c) => c,
        Err(_) => return false,
    };
    matches!(client.get(&url).send().await, Ok(r) if r.status().is_success())
}

/// Resolve `Settings.backend` to a concrete `BackendKind`. `Auto` delegates to
/// the existing platform detect; explicit settings win over detection.
fn resolve_backend_kind(setting: Backend) -> BackendKind {
    match setting {
        Backend::Auto => selector::detect_backend_kind(),
        Backend::LlamaCpp => BackendKind::LlamaCpp,
        Backend::Vllm => BackendKind::Vllm,
        Backend::Ollama => BackendKind::Ollama,
    }
}

/// Build the on-disk path the daemon expects for a model_id, matching the
/// convention used by `ocm_models::downloader::download_model`.
fn model_path_for(models_dir: &Path, model_id: &str) -> PathBuf {
    models_dir.join(format!("{model_id}.gguf"))
}

/// Decision: should bootstrap spawn + supervise `llama-server` on this run?
///
/// True iff ALL of:
/// - `Settings.backend = "llamacpp"` (explicit opt-in — Auto preserves
///   pre-v0.1.2 behavior, Ollama supervises itself, Vllm has its own path)
/// - `Settings.llama_server_binary` is `Some` (directive: None preserves
///   "do not spawn anything")
/// - `Settings.model_id` is `Some` AND the GGUF exists under `models_dir`
///   (conservative: don't burn the restart budget spawning a server that
///   has nothing to load — chat will fail loudly via the existing
///   "backend not reachable" message instead)
pub fn should_spawn_llama_supervisor(settings: &Settings, models_dir: &Path) -> bool {
    if !matches!(settings.backend, Backend::LlamaCpp) {
        return false;
    }
    if settings.llama_server_binary.is_none() {
        return false;
    }
    match settings.model_id.as_deref() {
        Some(id) => model_path_for(models_dir, id).exists(),
        None => false,
    }
}

/// Parse the port out of an `http://host:port/...` URL. Bare-bones to avoid
/// pulling in `url` for one field. Returns `None` if no port segment is found.
fn parse_port(url: &str) -> Option<u16> {
    // The last `:`-delimited segment, up to the first `/`.
    let after_colon = url.rsplit(':').next()?;
    let port_str = after_colon.split('/').next()?;
    port_str.parse().ok()
}

/// Build (but don't start) the llama-server Supervisor + its restart policy
/// for the current settings. Returns `None` if the spawn-gate
/// (`should_spawn_llama_supervisor`) refuses.
///
/// The caller is responsible for spawning `supervisor::supervise(...)` as a
/// background task and holding the resulting handle alive for the daemon's
/// lifetime (`main.rs` does this via Tauri-managed state + tokio task).
pub fn build_llama_supervisor(
    settings: &Settings,
    models_dir: &Path,
) -> Option<(Arc<Supervisor>, SupervisorPolicy)> {
    if !should_spawn_llama_supervisor(settings, models_dir) {
        return None;
    }
    let binary = PathBuf::from(settings.llama_server_binary.as_ref()?);
    let model_id = settings.model_id.as_ref()?;
    let model_path = model_path_for(models_dir, model_id);

    let inference_url = settings
        .inference_base_url
        .clone()
        .unwrap_or_else(|| DEFAULT_INFERENCE_BASE_URL.to_string());
    let port = parse_port(&inference_url).unwrap_or(8080);
    let health_url = format!("{inference_url}/v1/models");

    let sup = Arc::new(supervisor::spawn_llama_server(
        &binary,
        &model_path,
        port,
        supervisor::DEFAULT_LLAMA_CTX_LEN,
    ));
    let policy = SupervisorPolicy {
        health_url,
        ..SupervisorPolicy::default()
    };
    Some((sup, policy))
}

/// State the Tauri layer manages for the supervised subprocess. `status` is
/// shared with the supervise loop (which mutates it). `shutdown` is the sender
/// half of the cancellation channel; dropping it (or sending `true`) lets the
/// supervise loop exit cleanly. Held in a `Mutex<Option<_>>` so app exit can
/// `.take()` it.
pub struct LlamaSupervisorState {
    pub status: Arc<Mutex<SupervisorStatus>>,
    pub shutdown: Mutex<Option<tokio::sync::watch::Sender<bool>>>,
}

impl LlamaSupervisorState {
    pub fn not_spawning() -> Self {
        Self {
            status: Arc::new(Mutex::new(SupervisorStatus::NotSpawning)),
            shutdown: Mutex::new(None),
        }
    }

    pub fn live(
        status: Arc<Mutex<SupervisorStatus>>,
        shutdown_tx: tokio::sync::watch::Sender<bool>,
    ) -> Self {
        Self {
            status,
            shutdown: Mutex::new(Some(shutdown_tx)),
        }
    }
}

/// Construct the full AppState given settings.
pub fn build_app_state(settings: &Settings) -> ocm_api::AppState {
    let inference_url = settings
        .inference_base_url
        .clone()
        .unwrap_or_else(|| DEFAULT_INFERENCE_BASE_URL.to_string());
    let memory_url = settings
        .mem0_base_url
        .clone()
        .unwrap_or_else(|| DEFAULT_MEM0_BASE_URL.to_string());
    let ollama_url = settings
        .ollama_base_url
        .clone()
        .unwrap_or_else(|| DEFAULT_OLLAMA_BASE_URL.to_string());
    let ollama_model = settings
        .ollama_model
        .clone()
        .unwrap_or_else(|| DEFAULT_OLLAMA_MODEL.to_string());

    let kind = resolve_backend_kind(settings.backend);
    info!(backend = kind.as_str(), "selected inference backend");
    let backend = selector::make_backend_for_kind(kind, inference_url, ollama_url, ollama_model);
    let memory = Arc::new(ocm_memory::Mem0Client::new(memory_url, "ocm-default"));
    let backend: Arc<dyn ocm_inference::InferenceBackend> = Arc::from(backend);

    ocm_api::AppState {
        memory,
        backend,
        retrieval_top_k: settings.retrieval_top_k.unwrap_or(DEFAULT_RETRIEVAL_TOP_K),
    }
}

/// Spawn the OCM HTTP API server on the configured port. Runs forever; the
/// caller should not await this, but spawn it as a background task so the
/// Tauri main loop continues.
pub async fn run_api_server(state: ocm_api::AppState, port: u16) -> anyhow::Result<()> {
    let addr = SocketAddr::new(IpAddr::V4(Ipv4Addr::LOCALHOST), port);
    info!(%addr, "starting OCM API server");
    ocm_api::serve(addr, state).await
}

/// Run the full bootstrap sequence: probe dependencies, build state, spawn API.
/// This is the function the Tauri setup() closure invokes via a tokio task.
pub async fn bootstrap(settings: Settings) {
    let inference_url = settings
        .inference_base_url
        .clone()
        .unwrap_or_else(|| DEFAULT_INFERENCE_BASE_URL.to_string());
    let memory_url = settings
        .mem0_base_url
        .clone()
        .unwrap_or_else(|| DEFAULT_MEM0_BASE_URL.to_string());

    let status = probe_dependencies(&inference_url, &memory_url).await;
    if !status.inference_reachable {
        warn!(
            url = %inference_url,
            "inference backend not reachable at startup; chat will fail until backend is running"
        );
    } else {
        info!(url = %inference_url, "inference backend reachable");
    }
    if !status.memory_reachable {
        warn!(
            url = %memory_url,
            "Mem0 server not reachable at startup; retrieval will be disabled until it's running"
        );
    } else {
        info!(url = %memory_url, "Mem0 server reachable");
    }

    let state = build_app_state(&settings);
    let port = settings.api_port;

    if let Err(e) = run_api_server(state, port).await {
        warn!(error = ?e, "OCM API server exited with error");
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::settings::{Backend, Theme};

    fn test_settings() -> Settings {
        Settings {
            model_id: None,
            api_port: 17300,
            mcp_enabled: true,
            theme: Theme::System,
            inference_base_url: Some("http://127.0.0.1:18080".into()),
            mem0_base_url: Some("http://127.0.0.1:18765".into()),
            retrieval_top_k: Some(3),
            backend: Backend::Auto,
            ollama_base_url: None,
            ollama_model: None,
            llama_server_binary: None,
        }
    }

    #[test]
    fn parse_port_extracts_from_loopback_url() {
        assert_eq!(parse_port("http://127.0.0.1:8080"), Some(8080));
        assert_eq!(parse_port("http://127.0.0.1:8080/v1"), Some(8080));
        assert_eq!(parse_port("http://127.0.0.1:8000/v1/models"), Some(8000));
    }

    #[test]
    fn parse_port_returns_none_when_no_port() {
        assert_eq!(parse_port("http://example.com/v1"), None);
    }

    #[test]
    fn build_llama_supervisor_returns_none_when_spawn_gate_refuses() {
        let dir = tempfile::tempdir().unwrap();
        // Spawn-gate refuses (backend = Auto, no model file).
        let s = Settings::default();
        assert!(build_llama_supervisor(&s, dir.path()).is_none());
    }

    #[test]
    fn defaults_apply_when_settings_blank() {
        let s = Settings::default();
        // Settings::default supplies defaults for required fields and None for optionals.
        // build_app_state should fall back to DEFAULT_* constants for the optional URLs.
        let state = build_app_state(&s);
        assert_eq!(state.retrieval_top_k, DEFAULT_RETRIEVAL_TOP_K);
        // backend / memory clients are constructed; concrete name depends on platform
        // (Auto never picks Ollama — it's opt-in).
        let backend_name = state.backend.name();
        assert!(backend_name == "llama.cpp" || backend_name == "vLLM");
    }

    #[test]
    fn settings_override_defaults() {
        let s = test_settings();
        let state = build_app_state(&s);
        assert_eq!(state.retrieval_top_k, 3);
    }

    #[test]
    fn explicit_ollama_backend_is_wired_through_to_app_state() {
        // The headline v0.1.1 wiring assertion: a user who selects backend =
        // "ollama" in settings ends up with an Ollama InferenceBackend on the
        // live AppState. Verified by the trait's `name()` ("Ollama" — see
        // ocm_inference::ollama::Ollama::name).
        let s = Settings {
            backend: Backend::Ollama,
            ollama_base_url: Some("http://127.0.0.1:11434".into()),
            ollama_model: Some("llama3".into()),
            ..Settings::default()
        };
        let state = build_app_state(&s);
        assert_eq!(state.backend.name(), "Ollama");
    }

    #[test]
    fn explicit_ollama_uses_defaults_when_fields_unset() {
        // backend = "ollama" with no URL/model still produces a constructible
        // Ollama backend — bootstrap fills in the daemon's native defaults
        // (port 11434, the existing ollama::DEFAULT_MODEL).
        let s = Settings {
            backend: Backend::Ollama,
            ollama_base_url: None,
            ollama_model: None,
            ..Settings::default()
        };
        let state = build_app_state(&s);
        assert_eq!(state.backend.name(), "Ollama");
    }

    #[test]
    fn explicit_llamacpp_overrides_platform_detect() {
        // Users on a CUDA box who explicitly pick llama.cpp must get llama.cpp,
        // even if auto-detect would have picked vLLM.
        let s = Settings {
            backend: Backend::LlamaCpp,
            ..Settings::default()
        };
        let state = build_app_state(&s);
        assert_eq!(state.backend.name(), "llama.cpp");
    }

    #[test]
    fn explicit_vllm_overrides_platform_detect() {
        let s = Settings {
            backend: Backend::Vllm,
            ..Settings::default()
        };
        let state = build_app_state(&s);
        assert_eq!(state.backend.name(), "vLLM");
    }

    // --- Process supervision decision (Task 2 — Track 1 item 2) ---

    fn write_dummy_model(dir: &std::path::Path, model_id: &str) -> std::path::PathBuf {
        // Convention matches ocm_models::downloader::download_model:
        // dest = dest_dir.join(format!("{}.gguf", entry.id))
        let p = dir.join(format!("{model_id}.gguf"));
        std::fs::write(&p, b"").unwrap();
        p
    }

    #[test]
    fn should_spawn_llama_supervisor_yes_when_llamacpp_plus_binary_plus_model_present() {
        let dir = tempfile::tempdir().unwrap();
        write_dummy_model(dir.path(), "qwen2.5-1.5b-q4");
        let s = Settings {
            backend: Backend::LlamaCpp,
            model_id: Some("qwen2.5-1.5b-q4".into()),
            llama_server_binary: Some("/usr/local/bin/llama-server".into()),
            ..Settings::default()
        };
        assert!(should_spawn_llama_supervisor(&s, dir.path()));
    }

    #[test]
    fn should_spawn_llama_supervisor_no_when_backend_is_ollama() {
        // Headline rule per AGENT_OPERATIONS scope: Ollama supervises itself —
        // OCM must NEVER spawn anything when backend=ollama, regardless of the
        // other fields.
        let dir = tempfile::tempdir().unwrap();
        write_dummy_model(dir.path(), "qwen2.5-1.5b-q4");
        let s = Settings {
            backend: Backend::Ollama,
            model_id: Some("qwen2.5-1.5b-q4".into()),
            llama_server_binary: Some("/usr/local/bin/llama-server".into()),
            ..Settings::default()
        };
        assert!(!should_spawn_llama_supervisor(&s, dir.path()));
    }

    #[test]
    fn should_spawn_llama_supervisor_no_when_backend_is_auto() {
        // Auto leaves orchestration to the user's existing setup. Don't surprise
        // pre-v0.1.2 users who never opted into supervision.
        let dir = tempfile::tempdir().unwrap();
        write_dummy_model(dir.path(), "qwen2.5-1.5b-q4");
        let s = Settings {
            backend: Backend::Auto,
            model_id: Some("qwen2.5-1.5b-q4".into()),
            llama_server_binary: Some("/usr/local/bin/llama-server".into()),
            ..Settings::default()
        };
        assert!(!should_spawn_llama_supervisor(&s, dir.path()));
    }

    #[test]
    fn should_spawn_llama_supervisor_no_when_binary_unset() {
        // Directive: "llama-server binary path from settings, new field,
        // None = do-not-spawn preserves current behavior".
        let dir = tempfile::tempdir().unwrap();
        write_dummy_model(dir.path(), "qwen2.5-1.5b-q4");
        let s = Settings {
            backend: Backend::LlamaCpp,
            model_id: Some("qwen2.5-1.5b-q4".into()),
            llama_server_binary: None,
            ..Settings::default()
        };
        assert!(!should_spawn_llama_supervisor(&s, dir.path()));
    }

    #[test]
    fn should_spawn_llama_supervisor_no_when_model_file_missing() {
        // Conservative: refuse to spawn if there's nothing to load. The user
        // hasn't downloaded a model yet — let chat fail with the existing
        // "backend not reachable" message rather than burn the restart budget.
        let dir = tempfile::tempdir().unwrap();
        // intentionally no write_dummy_model
        let s = Settings {
            backend: Backend::LlamaCpp,
            model_id: Some("qwen2.5-1.5b-q4".into()),
            llama_server_binary: Some("/usr/local/bin/llama-server".into()),
            ..Settings::default()
        };
        assert!(!should_spawn_llama_supervisor(&s, dir.path()));
    }

    #[test]
    fn should_spawn_llama_supervisor_no_when_model_id_unset() {
        let dir = tempfile::tempdir().unwrap();
        let s = Settings {
            backend: Backend::LlamaCpp,
            model_id: None,
            llama_server_binary: Some("/usr/local/bin/llama-server".into()),
            ..Settings::default()
        };
        assert!(!should_spawn_llama_supervisor(&s, dir.path()));
    }

    #[tokio::test]
    async fn probe_url_returns_false_for_unreachable() {
        // Using port 1 (privileged, almost guaranteed not bound) on localhost
        let reachable = probe_url("http://127.0.0.1:1", "/health").await;
        assert!(!reachable, "port 1 should not be reachable in test env");
    }

    #[tokio::test]
    async fn probe_dependencies_reports_both_unreachable_when_neither_is_running() {
        let status = probe_dependencies("http://127.0.0.1:1", "http://127.0.0.1:2").await;
        assert!(!status.inference_reachable);
        assert!(!status.memory_reachable);
    }
}
