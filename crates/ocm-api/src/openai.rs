//! OpenAI-compat REST handlers.
//!
//! Endpoints:
//! - GET /v1/models — returns the list of available models
//! - POST /v1/chat/completions — non-streaming + streaming (delegates to streaming.rs)

use crate::AppState;
use axum::extract::State;
use axum::response::IntoResponse;
use axum::routing::{get, post};
use axum::{Json, Router};
use futures::StreamExt;
use serde::{Deserialize, Serialize};
use std::time::{SystemTime, UNIX_EPOCH};

#[derive(Debug, Clone, Serialize)]
pub struct ModelsResponse {
    pub object: &'static str,
    pub data: Vec<ModelEntry>,
}

#[derive(Debug, Clone, Serialize)]
pub struct ModelEntry {
    pub id: String,
    pub object: &'static str,
    pub created: u64,
    pub owned_by: &'static str,
}

#[derive(Debug, Clone, Deserialize)]
pub struct ChatCompletionRequest {
    pub model: Option<String>,
    pub messages: Vec<ChatMessageDto>,
    #[serde(default)]
    pub stream: bool,
    pub max_tokens: Option<u32>,
    pub temperature: Option<f32>,
    pub top_p: Option<f32>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct ChatMessageDto {
    pub role: String,
    pub content: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct ChatCompletionResponse {
    pub id: String,
    pub object: &'static str,
    pub created: u64,
    pub model: String,
    pub choices: Vec<Choice>,
}

#[derive(Debug, Clone, Serialize)]
pub struct Choice {
    pub index: u32,
    pub message: AssistantMessage,
    pub finish_reason: &'static str,
}

#[derive(Debug, Clone, Serialize)]
pub struct AssistantMessage {
    pub role: &'static str,
    pub content: String,
}

pub fn router() -> Router<AppState> {
    Router::new()
        .route("/models", get(list_models))
        .route("/chat/completions", post(chat_completions))
}

pub async fn list_models() -> Json<ModelsResponse> {
    Json(ModelsResponse {
        object: "list",
        data: vec![ModelEntry {
            id: "ocm-default".into(),
            object: "model",
            created: 0,
            owned_by: "opencircuitmodel",
        }],
    })
}

pub async fn chat_completions(
    State(state): State<AppState>,
    Json(req): Json<ChatCompletionRequest>,
) -> Result<axum::response::Response, axum::http::StatusCode> {
    if req.stream {
        return crate::streaming::stream_chat(state, req).await;
    }

    let last = req
        .messages
        .last()
        .ok_or(axum::http::StatusCode::BAD_REQUEST)?;

    // Library-driven retrieval per spec row 9: pull relevant memories
    // before the model runs, inject as context. Skip if retrieval_top_k == 0.
    let retrieved = if state.retrieval_top_k > 0 {
        match state.memory.search(&last.content, state.retrieval_top_k).await {
            Ok(results) => results,
            Err(e) => {
                tracing::warn!(error = ?e, "memory search failed; proceeding without retrieval");
                Vec::new()
            }
        }
    } else {
        Vec::new()
    };

    let messages = build_messages_with_retrieved(&req, &retrieved);

    let chat_req = ocm_inference::ChatRequest {
        messages,
        params: ocm_inference::GenerationParams {
            max_tokens: req.max_tokens,
            temperature: req.temperature,
            top_p: req.top_p,
            stop: vec![],
        },
    };

    let mut stream = state
        .backend
        .generate(chat_req)
        .await
        .map_err(|_| axum::http::StatusCode::BAD_GATEWAY)?;

    let mut content = String::new();
    while let Some(chunk) = stream.next().await {
        if let Ok(text) = chunk {
            content.push_str(&text);
        }
    }

    let body = ChatCompletionResponse {
        id: format!("chatcmpl-{}", uuid::Uuid::new_v4()),
        object: "chat.completion",
        created: now_secs(),
        model: req.model.unwrap_or_else(|| "ocm-default".into()),
        choices: vec![Choice {
            index: 0,
            message: AssistantMessage {
                role: "assistant",
                content,
            },
            finish_reason: "stop",
        }],
    };
    Ok((axum::http::StatusCode::OK, Json(body)).into_response())
}

/// Convert OpenAI-style messages to inference-layer messages, injecting
/// retrieved memories as a system message when present.
pub fn build_messages_with_retrieved(
    req: &ChatCompletionRequest,
    retrieved: &[ocm_memory::SearchResult],
) -> Vec<ocm_inference::ChatMessage> {
    let mut messages = Vec::with_capacity(req.messages.len() + 1);

    if !retrieved.is_empty() {
        let mut content = String::from("Relevant prior context:\n");
        for (i, r) in retrieved.iter().enumerate() {
            content.push_str(&format!("[{}] {}\n", i + 1, r.memory.text));
        }
        messages.push(ocm_inference::ChatMessage {
            role: ocm_inference::Role::System,
            content,
        });
    }

    for m in &req.messages {
        let role = match m.role.as_str() {
            "system" => ocm_inference::Role::System,
            "user" => ocm_inference::Role::User,
            "assistant" => ocm_inference::Role::Assistant,
            _ => ocm_inference::Role::User,
        };
        messages.push(ocm_inference::ChatMessage {
            role,
            content: m.content.clone(),
        });
    }

    messages
}

pub(crate) fn now_secs() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn dummy_search_result(text: &str, score: f32) -> ocm_memory::SearchResult {
        ocm_memory::SearchResult {
            memory: ocm_memory::Memory {
                id: ocm_memory::MemoryId(uuid::Uuid::new_v4().to_string()),
                text: text.to_string(),
                metadata: serde_json::Value::Null,
            },
            score,
        }
    }

    #[tokio::test]
    async fn list_models_returns_at_least_one() {
        let resp = list_models().await;
        assert_eq!(resp.object, "list");
        assert!(!resp.data.is_empty());
        assert_eq!(resp.data[0].id, "ocm-default");
    }

    #[test]
    fn build_messages_injects_retrieved_as_system() {
        let req = ChatCompletionRequest {
            model: None,
            messages: vec![ChatMessageDto {
                role: "user".into(),
                content: "what's my favorite color?".into(),
            }],
            stream: false,
            max_tokens: None,
            temperature: None,
            top_p: None,
        };
        let retrieved = vec![
            dummy_search_result("user said favorite color is teal", 0.92),
            dummy_search_result("user mentioned blue once", 0.55),
        ];
        let messages = build_messages_with_retrieved(&req, &retrieved);
        assert_eq!(messages.len(), 2);
        assert_eq!(messages[0].role, ocm_inference::Role::System);
        assert!(messages[0].content.contains("teal"));
        assert!(messages[0].content.contains("blue"));
        assert_eq!(messages[1].role, ocm_inference::Role::User);
        assert_eq!(messages[1].content, "what's my favorite color?");
    }

    #[test]
    fn build_messages_omits_system_when_no_retrieved() {
        let req = ChatCompletionRequest {
            model: None,
            messages: vec![ChatMessageDto {
                role: "user".into(),
                content: "hello".into(),
            }],
            stream: false,
            max_tokens: None,
            temperature: None,
            top_p: None,
        };
        let messages = build_messages_with_retrieved(&req, &[]);
        assert_eq!(messages.len(), 1);
        assert_eq!(messages[0].role, ocm_inference::Role::User);
    }

    #[test]
    fn build_messages_maps_unknown_role_to_user() {
        let req = ChatCompletionRequest {
            model: None,
            messages: vec![ChatMessageDto {
                role: "tool".into(),
                content: "tool output".into(),
            }],
            stream: false,
            max_tokens: None,
            temperature: None,
            top_p: None,
        };
        let messages = build_messages_with_retrieved(&req, &[]);
        assert_eq!(messages[0].role, ocm_inference::Role::User);
    }

    #[test]
    fn now_secs_is_after_2025() {
        // Simple sanity check that the timestamp helper returns a sensible value
        let t = now_secs();
        // 2025-01-01 = 1735689600 unix; anything past that is current time
        assert!(t > 1_735_689_600, "expected unix time after 2025-01-01");
    }
}
