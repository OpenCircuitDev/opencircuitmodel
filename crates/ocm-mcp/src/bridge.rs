//! Bridge from MCP tool calls to OCM HTTP API at localhost:7300.

use serde_json::{json, Value};

#[derive(Debug, thiserror::Error)]
pub enum BridgeError {
    #[error("HTTP transport: {0}")]
    Http(#[from] reqwest::Error),
    #[error("invalid arguments: {0}")]
    InvalidArgs(String),
    #[error("backend protocol: {0}")]
    Protocol(String),
}

/// HTTP client wrapping the OCM daemon's localhost:7300/v1 endpoints.
pub struct OcmBridge {
    base_url: String,
    http: reqwest::Client,
}

impl OcmBridge {
    pub fn new(base_url: impl Into<String>) -> Self {
        Self {
            base_url: base_url.into(),
            http: reqwest::Client::new(),
        }
    }

    // Used by tests + future diagnostic logging; kept on the public API so
    // callers can introspect which daemon URL the bridge is bound to.
    #[allow(dead_code)]
    pub fn base_url(&self) -> &str {
        &self.base_url
    }

    /// MCP tool: `chat` — forward a single user message to OCM's
    /// /v1/chat/completions and return the assistant's text.
    /// The OCM daemon handles library-driven retrieval (Mem0 search before
    /// the model runs) per spec row 9, so the MCP client doesn't need to
    /// know about memory at all.
    pub async fn chat(&self, message: &str) -> Result<String, BridgeError> {
        let body = json!({
            "model": "ocm-default",
            "messages": [{ "role": "user", "content": message }],
            "stream": false,
        });
        let resp = self
            .http
            .post(format!("{}/v1/chat/completions", self.base_url))
            .json(&body)
            .send()
            .await?
            .error_for_status()?;
        let payload: Value = resp.json().await?;
        payload
            .get("choices")
            .and_then(|c| c.get(0))
            .and_then(|c| c.get("message"))
            .and_then(|m| m.get("content"))
            .and_then(|c| c.as_str())
            .map(|s| s.to_string())
            .ok_or_else(|| BridgeError::Protocol("no choices[0].message.content".into()))
    }

    /// MCP tool: `list_models` — proxy /v1/models.
    pub async fn list_models(&self) -> Result<Vec<String>, BridgeError> {
        let resp = self
            .http
            .get(format!("{}/v1/models", self.base_url))
            .send()
            .await?
            .error_for_status()?;
        let payload: Value = resp.json().await?;
        let data = payload
            .get("data")
            .and_then(|d| d.as_array())
            .ok_or_else(|| BridgeError::Protocol("no data[] in /v1/models".into()))?;
        Ok(data
            .iter()
            .filter_map(|m| m.get("id").and_then(|v| v.as_str()).map(String::from))
            .collect())
    }
}

/// Extract a required string argument from an arbitrary JSON value.
pub fn arg_str(args: &Value, key: &str) -> Result<String, BridgeError> {
    args.get(key)
        .and_then(|v| v.as_str())
        .map(String::from)
        .ok_or_else(|| BridgeError::InvalidArgs(format!("missing or non-string '{key}'")))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn arg_str_extracts_value() {
        let v = json!({"message": "hello"});
        let s = arg_str(&v, "message").expect("extract");
        assert_eq!(s, "hello");
    }

    #[test]
    fn arg_str_errors_on_missing() {
        let v = json!({});
        let err = arg_str(&v, "message").expect_err("should fail");
        match err {
            BridgeError::InvalidArgs(msg) => assert!(msg.contains("'message'")),
            _ => panic!("expected InvalidArgs"),
        }
    }

    #[test]
    fn arg_str_errors_on_non_string() {
        let v = json!({"message": 42});
        let err = arg_str(&v, "message").expect_err("should fail");
        match err {
            BridgeError::InvalidArgs(_) => {}
            _ => panic!("expected InvalidArgs"),
        }
    }

    #[test]
    fn bridge_records_base_url() {
        let b = OcmBridge::new("http://localhost:7300");
        assert_eq!(b.base_url(), "http://localhost:7300");
    }
}
