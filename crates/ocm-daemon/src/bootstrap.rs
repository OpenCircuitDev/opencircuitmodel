//! Daemon startup orchestration — wires inference backend + memory client
//! + API server into a coherent boot sequence.
//!
//! Called from Tauri's setup() closure as a background tokio task. The OCM
//! daemon is *resilient by design*: if external dependencies (Mem0 server,
//! llama.cpp / vLLM) aren't running, the daemon stays up with degraded
//! functionality and logs warnings. The user gets a Tauri tray + window
//! that reports status; chat requests fail with clear errors.

use crate::settings::{Backend, Settings};
use ocm_inference::ollama::DEFAULT_MODEL as DEFAULT_OLLAMA_MODEL;
use ocm_inference::selector::{self, BackendKind, DEFAULT_OLLAMA_BASE_URL};
use std::net::{IpAddr, Ipv4Addr, SocketAddr};
use std::sync::Arc;
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
        }
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
