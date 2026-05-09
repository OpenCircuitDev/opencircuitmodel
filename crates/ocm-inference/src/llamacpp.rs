//! llama.cpp adapter — talks to a running `llama-server` process via OpenAI-compat endpoint.

use crate::{BackendError, ChatRequest, InferenceBackend, Role};
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
        Self {
            base_url: base_url.into(),
            http: Client::new(),
        }
    }

    pub fn base_url(&self) -> &str {
        &self.base_url
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

#[derive(Deserialize, Default)]
struct OaiDelta {
    #[serde(default)]
    content: Option<String>,
}

fn role_str(r: &Role) -> &'static str {
    match r {
        Role::System => "system",
        Role::User => "user",
        Role::Assistant => "assistant",
    }
}

/// Parse a single chunk of SSE bytes into the concatenated content delta.
/// Public so [`crate::vllm::Vllm`] can share the same parser.
pub(crate) fn parse_sse_chunk(text: &str) -> Result<String, BackendError> {
    let mut out = String::new();
    for line in text.lines() {
        let line = line.trim();
        if let Some(rest) = line.strip_prefix("data: ") {
            if rest == "[DONE]" {
                continue;
            }
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
}

#[async_trait]
impl InferenceBackend for LlamaCpp {
    fn name(&self) -> &'static str {
        "llama.cpp"
    }

    async fn health(&self) -> Result<(), BackendError> {
        let r = self
            .http
            .get(format!("{}/health", self.base_url))
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
        let messages: Vec<OaiMsg> = req
            .messages
            .iter()
            .map(|m| OaiMsg {
                role: role_str(&m.role),
                content: &m.content,
            })
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
        let resp = self
            .http
            .post(format!("{}/v1/chat/completions", self.base_url))
            .json(&body)
            .send()
            .await?
            .error_for_status()?;

        let stream = resp.bytes_stream().map(|chunk| {
            let bytes = chunk.map_err(BackendError::from)?;
            let text =
                std::str::from_utf8(&bytes).map_err(|e| BackendError::Protocol(e.to_string()))?;
            parse_sse_chunk(text)
        });
        Ok(stream.boxed())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_sse_concatenates_content_deltas() {
        let text = concat!(
            "data: {\"choices\":[{\"delta\":{\"content\":\"hello \"}}]}\n\n",
            "data: {\"choices\":[{\"delta\":{\"content\":\"world\"}}]}\n\n",
            "data: [DONE]\n\n",
        );
        let out = parse_sse_chunk(text).expect("parse");
        assert_eq!(out, "hello world");
    }

    #[test]
    fn parse_sse_ignores_done_markers() {
        let text = "data: [DONE]\n\n";
        let out = parse_sse_chunk(text).expect("parse");
        assert!(out.is_empty());
    }

    #[test]
    fn parse_sse_skips_malformed_lines() {
        let text = concat!(
            "junk line that should be skipped\n",
            "data: {\"choices\":[{\"delta\":{\"content\":\"ok\"}}]}\n\n",
        );
        let out = parse_sse_chunk(text).expect("parse");
        assert_eq!(out, "ok");
    }

    #[test]
    fn role_str_maps_correctly() {
        assert_eq!(role_str(&Role::System), "system");
        assert_eq!(role_str(&Role::User), "user");
        assert_eq!(role_str(&Role::Assistant), "assistant");
    }

    #[test]
    fn llamacpp_records_base_url() {
        let backend = LlamaCpp::new("http://localhost:8080");
        assert_eq!(backend.base_url(), "http://localhost:8080");
        assert_eq!(backend.name(), "llama.cpp");
    }
}
