//! Minimal MCP protocol types — JSON-RPC 2.0 over stdio per Anthropic's spec.
//!
//! We implement the subset OCM v1 needs: `initialize`, `tools/list`, `tools/call`.
//! Resources and prompts can be added in follow-ups when needed.

use serde::{Deserialize, Serialize};
use serde_json::Value;

#[derive(Debug, Clone, Deserialize)]
pub struct JsonRpcRequest {
    // Required by the JSON-RPC 2.0 wire format; serde validates presence
    // during parse. Kept for spec fidelity even though the bin path doesn't
    // re-read it after deserialize.
    #[allow(dead_code)]
    pub jsonrpc: String,
    /// Server-assigned (no "id" = notification, no response expected).
    #[serde(default)]
    pub id: Option<Value>,
    pub method: String,
    #[serde(default)]
    pub params: Value,
}

#[derive(Debug, Clone, Serialize)]
pub struct JsonRpcResponse {
    pub jsonrpc: &'static str,
    pub id: Value,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub result: Option<Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<JsonRpcError>,
}

#[derive(Debug, Clone, Serialize)]
pub struct JsonRpcError {
    pub code: i32,
    pub message: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub data: Option<Value>,
}

impl JsonRpcResponse {
    pub fn ok(id: Value, result: Value) -> Self {
        Self {
            jsonrpc: "2.0",
            id,
            result: Some(result),
            error: None,
        }
    }

    pub fn err(id: Value, code: i32, message: impl Into<String>) -> Self {
        Self {
            jsonrpc: "2.0",
            id,
            result: None,
            error: Some(JsonRpcError {
                code,
                message: message.into(),
                data: None,
            }),
        }
    }
}

/// MCP standard error codes (subset).
pub const METHOD_NOT_FOUND: i32 = -32601;
pub const INVALID_PARAMS: i32 = -32602;
pub const INTERNAL_ERROR: i32 = -32603;

/// MCP `initialize` response — server identity + capabilities.
pub fn initialize_result(server_name: &str, server_version: &str) -> Value {
    serde_json::json!({
        "protocolVersion": "2024-11-05",
        "serverInfo": {
            "name": server_name,
            "version": server_version,
        },
        "capabilities": {
            "tools": {},
        },
    })
}

/// MCP `tools/list` response — array of tool descriptions.
pub fn tools_list_result(tools: Vec<Value>) -> Value {
    serde_json::json!({ "tools": tools })
}

/// Build a single tool definition for `tools/list`.
pub fn tool(name: &str, description: &str, input_schema: Value) -> Value {
    serde_json::json!({
        "name": name,
        "description": description,
        "inputSchema": input_schema,
    })
}

/// MCP `tools/call` result wrapping content. Defaults to `text` content.
pub fn tools_call_text_result(text: String) -> Value {
    serde_json::json!({
        "content": [{ "type": "text", "text": text }],
        "isError": false,
    })
}

pub fn tools_call_error_result(text: String) -> Value {
    serde_json::json!({
        "content": [{ "type": "text", "text": text }],
        "isError": true,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_initialize_request() {
        let raw = r#"{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}"#;
        let req: JsonRpcRequest = serde_json::from_str(raw).expect("parse");
        assert_eq!(req.jsonrpc, "2.0");
        assert_eq!(req.method, "initialize");
        assert_eq!(req.id, Some(Value::Number(1.into())));
    }

    #[test]
    fn parse_notification_has_no_id() {
        let raw = r#"{"jsonrpc":"2.0","method":"notifications/initialized"}"#;
        let req: JsonRpcRequest = serde_json::from_str(raw).expect("parse");
        assert!(req.id.is_none());
    }

    #[test]
    fn ok_response_omits_error() {
        let resp = JsonRpcResponse::ok(Value::from(7), serde_json::json!({"x": 1}));
        let raw = serde_json::to_string(&resp).expect("serialize");
        assert!(raw.contains("\"result\""));
        assert!(!raw.contains("\"error\""));
    }

    #[test]
    fn err_response_omits_result() {
        let resp = JsonRpcResponse::err(Value::from(7), METHOD_NOT_FOUND, "no such method");
        let raw = serde_json::to_string(&resp).expect("serialize");
        assert!(raw.contains("\"error\""));
        assert!(!raw.contains("\"result\""));
        assert!(raw.contains(&format!("\"code\":{METHOD_NOT_FOUND}")));
    }

    #[test]
    fn initialize_result_has_server_info_and_capabilities() {
        let r = initialize_result("ocm", "0.1.0");
        assert_eq!(r["serverInfo"]["name"], "ocm");
        assert_eq!(r["serverInfo"]["version"], "0.1.0");
        assert!(r["capabilities"]["tools"].is_object());
    }

    #[test]
    fn tool_definition_includes_input_schema() {
        let t = tool(
            "chat",
            "Send a message",
            serde_json::json!({"type": "object", "properties": {"message": {"type": "string"}}}),
        );
        assert_eq!(t["name"], "chat");
        assert_eq!(t["inputSchema"]["type"], "object");
    }

    #[test]
    fn text_result_wraps_content() {
        let r = tools_call_text_result("hello world".into());
        assert_eq!(r["content"][0]["type"], "text");
        assert_eq!(r["content"][0]["text"], "hello world");
        assert_eq!(r["isError"], false);
    }

    #[test]
    fn error_result_marks_is_error_true() {
        let r = tools_call_error_result("backend down".into());
        assert_eq!(r["isError"], true);
    }
}
