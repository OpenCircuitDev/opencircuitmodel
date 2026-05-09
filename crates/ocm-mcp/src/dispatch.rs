//! Dispatch JSON-RPC requests to the appropriate handler.
//! Pure-logic module — testable without spawning a subprocess.

use crate::bridge::{arg_str, BridgeError, OcmBridge};
use crate::protocol::{
    initialize_result, tool, tools_call_error_result, tools_call_text_result,
    tools_list_result, JsonRpcRequest, JsonRpcResponse, INTERNAL_ERROR, INVALID_PARAMS,
    METHOD_NOT_FOUND,
};
use serde_json::{json, Value};

const SERVER_NAME: &str = "ocm-mcp";
const SERVER_VERSION: &str = env!("CARGO_PKG_VERSION");

/// All tools we expose. Used by `tools/list` and validated by `tools/call`.
pub fn declare_tools() -> Vec<Value> {
    vec![
        tool(
            "chat",
            "Send a message to the OpenCircuitModel personal AI agent and receive a reply. The agent has persistent memory across sessions and library-driven retrieval (Mem0). Returns the assistant's text response.",
            json!({
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "The user's message to send to the agent."
                    }
                },
                "required": ["message"]
            }),
        ),
        tool(
            "list_models",
            "List the models available to the OCM daemon. Returns an array of model IDs (typically ['ocm-default']).",
            json!({
                "type": "object",
                "properties": {}
            }),
        ),
    ]
}

/// Dispatch a single JSON-RPC request. Returns None for notifications
/// (no response to send back).
pub async fn dispatch(req: JsonRpcRequest, bridge: &OcmBridge) -> Option<JsonRpcResponse> {
    let id = req.id.clone()?;

    match req.method.as_str() {
        "initialize" => Some(JsonRpcResponse::ok(
            id,
            initialize_result(SERVER_NAME, SERVER_VERSION),
        )),
        "tools/list" => Some(JsonRpcResponse::ok(id, tools_list_result(declare_tools()))),
        "tools/call" => Some(handle_tools_call(id, &req.params, bridge).await),
        // Catch-all for unknown methods. Notifications don't get errors;
        // requests with unknown methods do.
        _ => Some(JsonRpcResponse::err(
            id,
            METHOD_NOT_FOUND,
            format!("unknown method: {}", req.method),
        )),
    }
}

async fn handle_tools_call(id: Value, params: &Value, bridge: &OcmBridge) -> JsonRpcResponse {
    let name = match params.get("name").and_then(|v| v.as_str()) {
        Some(n) => n,
        None => {
            return JsonRpcResponse::err(id, INVALID_PARAMS, "missing 'name' in tools/call");
        }
    };
    let args = params.get("arguments").cloned().unwrap_or(json!({}));

    let result = match name {
        "chat" => match arg_str(&args, "message") {
            Ok(message) => match bridge.chat(&message).await {
                Ok(reply) => tools_call_text_result(reply),
                Err(BridgeError::Http(e)) => {
                    tools_call_error_result(format!("OCM daemon unreachable: {e}"))
                }
                Err(e) => tools_call_error_result(e.to_string()),
            },
            Err(e) => return JsonRpcResponse::err(id, INVALID_PARAMS, e.to_string()),
        },
        "list_models" => match bridge.list_models().await {
            Ok(models) => tools_call_text_result(models.join("\n")),
            Err(e) => tools_call_error_result(e.to_string()),
        },
        unknown => {
            return JsonRpcResponse::err(
                id,
                METHOD_NOT_FOUND,
                format!("unknown tool: {unknown}"),
            );
        }
    };

    match serde_json::to_value(&result) {
        Ok(v) => JsonRpcResponse::ok(id, v),
        Err(e) => JsonRpcResponse::err(id, INTERNAL_ERROR, format!("serialize: {e}")),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn parse_req(json_str: &str) -> JsonRpcRequest {
        serde_json::from_str(json_str).expect("parse")
    }

    fn dummy_bridge() -> OcmBridge {
        // Use a guaranteed-unreachable URL so tests don't depend on a live daemon.
        // Tools that try to call HTTP will get an HTTP error, which we test for.
        OcmBridge::new("http://127.0.0.1:1")
    }

    #[tokio::test]
    async fn initialize_returns_server_info() {
        let req = parse_req(r#"{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}"#);
        let resp = dispatch(req, &dummy_bridge()).await.expect("response");
        let result = resp.result.expect("ok");
        assert_eq!(result["serverInfo"]["name"], "ocm-mcp");
    }

    #[tokio::test]
    async fn tools_list_returns_chat_and_list_models() {
        let req = parse_req(r#"{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}"#);
        let resp = dispatch(req, &dummy_bridge()).await.expect("response");
        let result = resp.result.expect("ok");
        let names: Vec<&str> = result["tools"]
            .as_array()
            .unwrap()
            .iter()
            .map(|t| t["name"].as_str().unwrap())
            .collect();
        assert!(names.contains(&"chat"));
        assert!(names.contains(&"list_models"));
    }

    #[tokio::test]
    async fn unknown_method_returns_method_not_found() {
        let req = parse_req(r#"{"jsonrpc":"2.0","id":3,"method":"bogus/thing","params":{}}"#);
        let resp = dispatch(req, &dummy_bridge()).await.expect("response");
        assert!(resp.result.is_none());
        let err = resp.error.expect("error");
        assert_eq!(err.code, METHOD_NOT_FOUND);
    }

    #[tokio::test]
    async fn notification_returns_no_response() {
        let req = parse_req(r#"{"jsonrpc":"2.0","method":"notifications/initialized"}"#);
        let resp = dispatch(req, &dummy_bridge()).await;
        assert!(resp.is_none(), "notifications should not produce a response");
    }

    #[tokio::test]
    async fn tools_call_chat_missing_message_returns_invalid_params() {
        let req = parse_req(
            r#"{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"chat","arguments":{}}}"#,
        );
        let resp = dispatch(req, &dummy_bridge()).await.expect("response");
        let err = resp.error.expect("error");
        assert_eq!(err.code, INVALID_PARAMS);
        assert!(err.message.contains("'message'"));
    }

    #[tokio::test]
    async fn tools_call_chat_with_unreachable_backend_returns_text_error() {
        let req = parse_req(
            r#"{"jsonrpc":"2.0","id":5,"method":"tools/call","params":{"name":"chat","arguments":{"message":"hi"}}}"#,
        );
        let resp = dispatch(req, &dummy_bridge()).await.expect("response");
        // Result is OK at the JSON-RPC level — MCP encodes tool errors *inside* the result
        // (with isError: true), not as JSON-RPC errors.
        let result = resp.result.expect("ok");
        assert_eq!(result["isError"], true);
    }

    #[tokio::test]
    async fn tools_call_unknown_tool_returns_method_not_found() {
        let req = parse_req(
            r#"{"jsonrpc":"2.0","id":6,"method":"tools/call","params":{"name":"bogus","arguments":{}}}"#,
        );
        let resp = dispatch(req, &dummy_bridge()).await.expect("response");
        let err = resp.error.expect("error");
        assert_eq!(err.code, METHOD_NOT_FOUND);
    }

    #[tokio::test]
    async fn tools_call_missing_name_returns_invalid_params() {
        let req = parse_req(
            r#"{"jsonrpc":"2.0","id":7,"method":"tools/call","params":{"arguments":{}}}"#,
        );
        let resp = dispatch(req, &dummy_bridge()).await.expect("response");
        let err = resp.error.expect("error");
        assert_eq!(err.code, INVALID_PARAMS);
        assert!(err.message.contains("'name'"));
    }

    #[test]
    fn declare_tools_returns_at_least_two() {
        let tools = declare_tools();
        assert!(tools.len() >= 2);
    }
}
