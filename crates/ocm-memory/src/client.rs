//! Mem0 OpenMemory REST client.
//!
//! The Mem0 OpenMemory MCP server exposes a small REST surface over its local
//! Postgres + Qdrant backing store. This client wraps the subset OCM v1 needs:
//! `health`, `add`, `search`, `get`. Other Mem0 endpoints (delete, update,
//! conversation history) land in later phases.
//!
//! Endpoint convention: `<base_url>/v1/memories/...`. Adapt against current
//! Mem0 OSS server when integrating — the API surface is stable but version
//! pin matters.

use reqwest::Client;
use serde::{Deserialize, Serialize};

/// Stable identifier for a stored memory.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, Hash)]
pub struct MemoryId(pub String);

/// A single memory: text content + opaque metadata.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Memory {
    pub id: MemoryId,
    pub text: String,
    #[serde(default)]
    pub metadata: serde_json::Value,
}

/// One result returned from a similarity search.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SearchResult {
    pub memory: Memory,
    pub score: f32,
}

#[derive(Debug, thiserror::Error)]
pub enum Mem0Error {
    #[error("Mem0 transport: {0}")]
    Transport(#[from] reqwest::Error),
    #[error("Mem0 protocol: {0}")]
    Protocol(String),
    #[error("Mem0 not ready: {0}")]
    NotReady(String),
}

#[derive(Serialize)]
struct AddRequest<'a> {
    text: &'a str,
    user_id: &'a str,
    #[serde(skip_serializing_if = "Option::is_none")]
    metadata: Option<&'a serde_json::Value>,
}

#[derive(Serialize)]
struct SearchRequest<'a> {
    query: &'a str,
    user_id: &'a str,
    #[serde(skip_serializing_if = "Option::is_none")]
    limit: Option<u32>,
}

pub struct Mem0Client {
    base_url: String,
    user_id: String,
    http: Client,
}

impl Mem0Client {
    /// Construct a Mem0 client targeting `base_url` for memories scoped to `user_id`.
    /// Mem0 partitions all memories by user_id; this maps directly to the OCM
    /// "single-tenant local daemon" model from spec v0.4 (each OCM install = one user_id).
    pub fn new(base_url: impl Into<String>, user_id: impl Into<String>) -> Self {
        Self {
            base_url: base_url.into(),
            user_id: user_id.into(),
            http: Client::new(),
        }
    }

    pub fn base_url(&self) -> &str {
        &self.base_url
    }

    pub fn user_id(&self) -> &str {
        &self.user_id
    }

    pub async fn health(&self) -> Result<(), Mem0Error> {
        let r = self
            .http
            .get(format!("{}/v1/health", self.base_url))
            .send()
            .await?;
        if r.status().is_success() {
            Ok(())
        } else {
            Err(Mem0Error::NotReady(r.status().to_string()))
        }
    }

    /// Add a memory. Returns the assigned id.
    pub async fn add(
        &self,
        text: &str,
        metadata: Option<&serde_json::Value>,
    ) -> Result<MemoryId, Mem0Error> {
        let body = AddRequest {
            text,
            user_id: &self.user_id,
            metadata,
        };
        let response = self
            .http
            .post(format!("{}/v1/memories", self.base_url))
            .json(&body)
            .send()
            .await?
            .error_for_status()?;
        let parsed: serde_json::Value = response.json().await?;
        let id = parsed
            .get("id")
            .and_then(|v| v.as_str())
            .ok_or_else(|| Mem0Error::Protocol("response missing 'id'".into()))?;
        Ok(MemoryId(id.to_string()))
    }

    /// Library-driven retrieval — caller queries before the model's turn and
    /// feeds the results into the model's context. The model never decides
    /// when to retrieve.
    pub async fn search(&self, query: &str, limit: u32) -> Result<Vec<SearchResult>, Mem0Error> {
        let body = SearchRequest {
            query,
            user_id: &self.user_id,
            limit: Some(limit),
        };
        let response = self
            .http
            .post(format!("{}/v1/memories/search", self.base_url))
            .json(&body)
            .send()
            .await?
            .error_for_status()?;
        let parsed: serde_json::Value = response.json().await?;
        let results_array = parsed
            .get("results")
            .and_then(|v| v.as_array())
            .ok_or_else(|| Mem0Error::Protocol("response missing 'results' array".into()))?;
        let mut out = Vec::with_capacity(results_array.len());
        for entry in results_array {
            let memory = parse_memory(entry)?;
            let score = entry
                .get("score")
                .and_then(|v| v.as_f64())
                .ok_or_else(|| Mem0Error::Protocol("result missing 'score'".into()))?;
            out.push(SearchResult {
                memory,
                score: score as f32,
            });
        }
        Ok(out)
    }

    /// Fetch a memory by id.
    pub async fn get(&self, id: &MemoryId) -> Result<Memory, Mem0Error> {
        let response = self
            .http
            .get(format!("{}/v1/memories/{}", self.base_url, id.0))
            .send()
            .await?
            .error_for_status()?;
        let parsed: serde_json::Value = response.json().await?;
        parse_memory(&parsed)
    }
}

fn parse_memory(value: &serde_json::Value) -> Result<Memory, Mem0Error> {
    let id = value
        .get("id")
        .and_then(|v| v.as_str())
        .ok_or_else(|| Mem0Error::Protocol("memory missing 'id'".into()))?;
    let text = value
        .get("text")
        .and_then(|v| v.as_str())
        .ok_or_else(|| Mem0Error::Protocol("memory missing 'text'".into()))?;
    let metadata = value
        .get("metadata")
        .cloned()
        .unwrap_or(serde_json::Value::Null);
    Ok(Memory {
        id: MemoryId(id.to_string()),
        text: text.to_string(),
        metadata,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn memory_id_round_trips() {
        let id = MemoryId("abc-123".to_string());
        let s = serde_json::to_string(&id).expect("serialize");
        let back: MemoryId = serde_json::from_str(&s).expect("deserialize");
        assert_eq!(back, id);
    }

    #[test]
    fn parse_memory_extracts_id_text_metadata() {
        let v = serde_json::json!({
            "id": "mem-42",
            "text": "the user prefers terse responses",
            "metadata": {"source": "conversation", "session": "abc"},
        });
        let m = parse_memory(&v).expect("parse");
        assert_eq!(m.id.0, "mem-42");
        assert_eq!(m.text, "the user prefers terse responses");
        assert_eq!(m.metadata["source"], "conversation");
    }

    #[test]
    fn parse_memory_missing_id_errors() {
        let v = serde_json::json!({"text": "no id here"});
        let err = parse_memory(&v).expect_err("should fail");
        match err {
            Mem0Error::Protocol(msg) => assert!(msg.contains("'id'")),
            _ => panic!("expected Protocol error"),
        }
    }

    #[test]
    fn parse_memory_missing_text_errors() {
        let v = serde_json::json!({"id": "mem-42"});
        let err = parse_memory(&v).expect_err("should fail");
        match err {
            Mem0Error::Protocol(msg) => assert!(msg.contains("'text'")),
            _ => panic!("expected Protocol error"),
        }
    }

    #[test]
    fn parse_memory_handles_missing_metadata() {
        let v = serde_json::json!({
            "id": "mem-42",
            "text": "no metadata field",
        });
        let m = parse_memory(&v).expect("parse");
        assert_eq!(m.metadata, serde_json::Value::Null);
    }

    #[test]
    fn client_records_base_url_and_user() {
        let client = Mem0Client::new("http://localhost:8765", "ocm-default");
        assert_eq!(client.base_url(), "http://localhost:8765");
        assert_eq!(client.user_id(), "ocm-default");
    }
}
