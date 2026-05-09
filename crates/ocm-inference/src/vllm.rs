//! vLLM adapter — same OpenAI-compat wire format as llama.cpp; shares the SSE parser.
//!
//! vLLM exposes `/v1/models` always; older versions had `/health`, newer ones may not.
//! Health check probes `/v1/models` for compatibility.

use crate::{llamacpp::LlamaCpp, BackendError, ChatRequest, InferenceBackend};
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

    pub fn base_url(&self) -> &str {
        &self.base_url
    }
}

#[async_trait]
impl InferenceBackend for Vllm {
    fn name(&self) -> &'static str {
        "vLLM"
    }

    async fn health(&self) -> Result<(), BackendError> {
        let r = self
            .http
            .get(format!("{}/v1/models", self.base_url))
            .send()
            .await?;
        if r.status().is_success() {
            Ok(())
        } else {
            Err(BackendError::NotReady(r.status().to_string()))
        }
    }

    async fn generate(
        &self,
        req: ChatRequest,
    ) -> Result<BoxStream<'static, Result<String, BackendError>>, BackendError> {
        self.inner.generate(req).await
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn vllm_records_base_url() {
        let backend = Vllm::new("http://localhost:8000");
        assert_eq!(backend.base_url(), "http://localhost:8000");
        assert_eq!(backend.name(), "vLLM");
    }
}
