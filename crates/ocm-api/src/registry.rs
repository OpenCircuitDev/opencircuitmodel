//! Registry endpoints — exposes the bundled model registry over HTTP so any
//! client (frontend, Cline, Continue.dev, etc.) can browse what's available.
//! Downloading is gated through the Tauri command (filesystem access) and
//! is NOT exposed via HTTP — registry listing is purely informational here.

use crate::AppState;
use axum::routing::get;
use axum::{Json, Router};
use ocm_models::Registry;

pub fn router() -> Router<AppState> {
    Router::new().route("/models", get(list_registry_models))
}

pub async fn list_registry_models() -> Result<Json<Registry>, axum::http::StatusCode> {
    Registry::load_bundled()
        .map(Json)
        .map_err(|e| {
            tracing::error!(error = ?e, "bundled registry failed to parse — corrupted build artifact?");
            axum::http::StatusCode::INTERNAL_SERVER_ERROR
        })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn list_registry_returns_at_least_one_model() {
        let resp = list_registry_models().await.expect("ok");
        let registry = &resp.0;
        assert_eq!(registry.version, 1);
        assert!(!registry.models.is_empty());
    }
}
