//! OCM API surface — OpenAI-compatible HTTP server (and MCP server adapter, future).
//!
//! Per spec v0.4 row 11: client-facing API is OpenAI-compat HTTP + MCP. Covers ~95%
//! of existing clients on day 1 (Claude Code, Cursor, Cline, Continue.dev, ChatGPT,
//! Gemini, Vercel AI SDK, etc.).
//!
//! This crate exposes the HTTP server. The daemon constructs an `AppState`
//! containing the live `Mem0Client` and `InferenceBackend`, then calls `serve()`.
//!
//! Library-driven retrieval pattern (spec row 9): the API layer calls
//! `Mem0Client::search` BEFORE forwarding the chat request to the inference
//! backend, so the model receives retrieved context as part of the prompt.
//! The model never has to drive its own memory tool.

use axum::Router;
use std::net::SocketAddr;
use std::sync::Arc;
use tracing::info;

pub mod auth;
pub mod openai;
pub mod streaming;

/// Shared state passed to every handler.
#[derive(Clone)]
pub struct AppState {
    pub memory: Arc<ocm_memory::Mem0Client>,
    pub backend: Arc<dyn ocm_inference::InferenceBackend>,
    /// Number of memories to retrieve per chat turn (0 = retrieval disabled)
    pub retrieval_top_k: u32,
}

/// Construct the full router with /v1/* OpenAI-compat routes.
pub fn router(state: AppState) -> Router {
    Router::new()
        .nest("/v1", openai::router())
        .with_state(state)
        .layer(tower_http::trace::TraceLayer::new_for_http())
}

/// Bind and serve. Loopback-only by default; external callers go via the
/// localhost auth middleware.
pub async fn serve(addr: SocketAddr, state: AppState) -> anyhow::Result<()> {
    let app = router(state);
    let listener = tokio::net::TcpListener::bind(addr).await?;
    info!(%addr, "OCM API listening (OpenAI-compat HTTP)");
    axum::serve(
        listener,
        app.into_make_service_with_connect_info::<SocketAddr>(),
    )
    .await?;
    Ok(())
}
