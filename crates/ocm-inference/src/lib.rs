//! Inference backend trait + adapters for OCM.
//!
//! Two production backends targeted by v1:
//! - [`llamacpp::LlamaCpp`] — Apple Silicon default (Metal) and CPU-only fallback
//! - [`vllm::Vllm`] — NVIDIA default (CUDA + AWQ-INT4 + RadixAttention via SGLang upgrade path)
//!
//! Both expose the same OpenAI-compatible HTTP wire format, so most adapter logic is
//! shared via [`llamacpp::LlamaCpp`] and [`vllm::Vllm`] re-uses it.

use async_trait::async_trait;
use futures::stream::BoxStream;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ChatMessage {
    pub role: Role,
    pub content: String,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "lowercase")]
pub enum Role {
    System,
    User,
    Assistant,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct GenerationParams {
    pub max_tokens: Option<u32>,
    pub temperature: Option<f32>,
    pub top_p: Option<f32>,
    #[serde(default)]
    pub stop: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChatRequest {
    pub messages: Vec<ChatMessage>,
    #[serde(default)]
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
pub mod selector;
pub mod vllm;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn role_serializes_lowercase() {
        let msg = ChatMessage {
            role: Role::User,
            content: "hi".into(),
        };
        let s = serde_json::to_string(&msg).expect("serialize");
        assert!(s.contains("\"role\":\"user\""));
    }

    #[test]
    fn generation_params_defaults() {
        let p = GenerationParams::default();
        assert!(p.max_tokens.is_none());
        assert!(p.stop.is_empty());
    }

    #[test]
    fn chat_request_round_trips() {
        let req = ChatRequest {
            messages: vec![ChatMessage {
                role: Role::System,
                content: "be terse".into(),
            }],
            params: GenerationParams {
                max_tokens: Some(64),
                temperature: Some(0.0),
                ..Default::default()
            },
        };
        let s = serde_json::to_string(&req).expect("serialize");
        let back: ChatRequest = serde_json::from_str(&s).expect("deserialize");
        assert_eq!(back.messages.len(), 1);
        assert_eq!(back.params.max_tokens, Some(64));
    }
}
