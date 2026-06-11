//! Ollama adapter — talks to a running Ollama daemon via its native NDJSON API.
//!
//! Why a third backend: Ollama is the largest installed base of local-model users,
//! and an existing Ollama daemon (default `127.0.0.1:11434`) already supervises model
//! load/unload. Pointing OCM at it gives those users a zero-extra-process path — no
//! separate `llama-server` to manage. The daemon + model class this adapter targets
//! was exercised end-to-end by the `bench/isolation/memory/amnesia-ab` sandbox
//! (verdict CONFIRMED, 2026-06-11).
//!
//! Unlike llama.cpp/vLLM, Ollama's native streaming format is NDJSON (one JSON object
//! per line, final line carries `"done":true`), and the model tag is REQUIRED in every
//! request — there is no server-side default model.

use crate::{BackendError, ChatRequest, InferenceBackend, Role};
use async_trait::async_trait;
use futures::stream::BoxStream;
use futures::StreamExt;
use reqwest::Client;
use serde::{Deserialize, Serialize};

/// Default model tag when none is configured.
pub const DEFAULT_MODEL: &str = "llama3";

pub struct Ollama {
    base_url: String,
    model: String,
    http: Client,
}

impl Ollama {
    pub fn new(base_url: impl Into<String>, model: impl Into<String>) -> Self {
        Self {
            base_url: base_url.into(),
            model: model.into(),
            http: Client::new(),
        }
    }

    pub fn base_url(&self) -> &str {
        &self.base_url
    }

    pub fn model(&self) -> &str {
        &self.model
    }
}

#[derive(Serialize)]
struct OllamaChatBody<'a> {
    model: &'a str,
    messages: Vec<OllamaMsg<'a>>,
    stream: bool,
    options: OllamaOptions,
}

#[derive(Serialize)]
struct OllamaMsg<'a> {
    role: &'a str,
    content: &'a str,
}

/// Generation params live under `options` in Ollama's native API; note
/// `max_tokens` maps to `num_predict`.
#[derive(Serialize, Default)]
struct OllamaOptions {
    #[serde(skip_serializing_if = "Option::is_none")]
    num_predict: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    temperature: Option<f32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    top_p: Option<f32>,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    stop: Vec<String>,
}

#[derive(Deserialize)]
struct OllamaChunk {
    #[serde(default)]
    message: Option<OllamaChunkMsg>,
}

#[derive(Deserialize)]
struct OllamaChunkMsg {
    #[serde(default)]
    content: String,
}

fn role_str(r: &Role) -> &'static str {
    match r {
        Role::System => "system",
        Role::User => "user",
        Role::Assistant => "assistant",
    }
}

/// Parse a chunk of NDJSON lines into the concatenated content delta.
/// The `"done":true` line carries an empty `message.content`, so it needs no
/// special-casing — it simply contributes nothing.
pub(crate) fn parse_ndjson_chunk(text: &str) -> Result<String, BackendError> {
    let mut out = String::new();
    for line in text.lines() {
        let line = line.trim();
        if line.is_empty() {
            continue;
        }
        if let Ok(c) = serde_json::from_str::<OllamaChunk>(line) {
            if let Some(m) = c.message {
                out.push_str(&m.content);
            }
        }
    }
    Ok(out)
}

#[async_trait]
impl InferenceBackend for Ollama {
    fn name(&self) -> &'static str {
        "Ollama"
    }

    async fn health(&self) -> Result<(), BackendError> {
        let r = self
            .http
            .get(format!("{}/api/tags", self.base_url))
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
        let messages: Vec<OllamaMsg> = req
            .messages
            .iter()
            .map(|m| OllamaMsg {
                role: role_str(&m.role),
                content: &m.content,
            })
            .collect();
        let body = OllamaChatBody {
            model: &self.model,
            messages,
            stream: true,
            options: OllamaOptions {
                num_predict: req.params.max_tokens,
                temperature: req.params.temperature,
                top_p: req.params.top_p,
                stop: req.params.stop.clone(),
            },
        };
        let resp = self
            .http
            .post(format!("{}/api/chat", self.base_url))
            .json(&body)
            .send()
            .await?
            .error_for_status()?;

        let stream = resp.bytes_stream().map(|chunk| {
            let bytes = chunk.map_err(BackendError::from)?;
            let text =
                std::str::from_utf8(&bytes).map_err(|e| BackendError::Protocol(e.to_string()))?;
            parse_ndjson_chunk(text)
        });
        Ok(stream.boxed())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    // Fixtures below are VERBATIM captures from a live Ollama 127.0.0.1:11434
    // /api/chat stream (llama3, 2026-06-11) — the parser is pinned to the real
    // wire format, not to documentation.

    #[test]
    fn parse_ndjson_concatenates_content_deltas() {
        let text = concat!(
            "{\"model\":\"llama3\",\"created_at\":\"2026-06-11T20:39:22.6565791Z\",\"message\":{\"role\":\"assistant\",\"content\":\"Hi\"},\"done\":false}\n",
            "{\"model\":\"llama3\",\"created_at\":\"2026-06-11T20:39:22.7598978Z\",\"message\":{\"role\":\"assistant\",\"content\":\"!\"},\"done\":false}\n",
        );
        let out = parse_ndjson_chunk(text).expect("parse");
        assert_eq!(out, "Hi!");
    }

    #[test]
    fn parse_ndjson_done_line_contributes_nothing() {
        let text = "{\"model\":\"llama3\",\"created_at\":\"2026-06-11T20:39:22.8736917Z\",\"message\":{\"role\":\"assistant\",\"content\":\"\"},\"done\":true,\"done_reason\":\"stop\",\"total_duration\":6912063700,\"load_duration\":5972558500,\"prompt_eval_count\":14,\"prompt_eval_duration\":706919000,\"eval_count\":3,\"eval_duration\":227366000}\n";
        let out = parse_ndjson_chunk(text).expect("parse");
        assert!(out.is_empty());
    }

    #[test]
    fn parse_ndjson_skips_malformed_and_blank_lines() {
        let text = concat!(
            "not json at all\n",
            "\n",
            "{\"message\":{\"role\":\"assistant\",\"content\":\"ok\"},\"done\":false}\n",
        );
        let out = parse_ndjson_chunk(text).expect("parse");
        assert_eq!(out, "ok");
    }

    #[test]
    fn options_serialize_under_ollama_names() {
        let opts = OllamaOptions {
            num_predict: Some(64),
            temperature: Some(0.2),
            top_p: None,
            stop: vec![],
        };
        let s = serde_json::to_string(&opts).expect("serialize");
        assert!(s.contains("\"num_predict\":64"));
        assert!(!s.contains("top_p"));
        assert!(!s.contains("stop"));
    }

    #[test]
    fn role_str_maps_correctly() {
        assert_eq!(role_str(&Role::System), "system");
        assert_eq!(role_str(&Role::User), "user");
        assert_eq!(role_str(&Role::Assistant), "assistant");
    }

    #[test]
    fn ollama_records_base_url_and_model() {
        let backend = Ollama::new("http://127.0.0.1:11434", DEFAULT_MODEL);
        assert_eq!(backend.base_url(), "http://127.0.0.1:11434");
        assert_eq!(backend.model(), "llama3");
        assert_eq!(backend.name(), "Ollama");
    }
}
