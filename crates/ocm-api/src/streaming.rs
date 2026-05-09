//! SSE streaming for /v1/chat/completions when stream=true.

use crate::openai::{build_messages_with_retrieved, now_secs, ChatCompletionRequest};
use crate::AppState;
use async_stream::stream;
use axum::body::Body;
use axum::http::{Response, StatusCode};
use futures::StreamExt;
use serde_json::json;

pub async fn stream_chat(
    state: AppState,
    req: ChatCompletionRequest,
) -> Result<Response<Body>, StatusCode> {
    let last_text = req
        .messages
        .last()
        .ok_or(StatusCode::BAD_REQUEST)?
        .content
        .clone();
    let model = req.model.clone().unwrap_or_else(|| "ocm-default".into());
    let id = format!("chatcmpl-{}", uuid::Uuid::new_v4());

    // Library-driven retrieval before the model runs (per spec row 9).
    let retrieved = if state.retrieval_top_k > 0 {
        match state.memory.search(&last_text, state.retrieval_top_k).await {
            Ok(r) => r,
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

    let mut backend_stream = state
        .backend
        .generate(chat_req)
        .await
        .map_err(|_| StatusCode::BAD_GATEWAY)?;

    let id_for_stream = id.clone();
    let model_for_stream = model.clone();
    let body_stream = stream! {
        while let Some(chunk_res) = backend_stream.next().await {
            let chunk = match chunk_res { Ok(s) => s, Err(_) => break };
            if chunk.is_empty() { continue; }
            let event = json!({
                "id": id_for_stream,
                "object": "chat.completion.chunk",
                "created": now_secs(),
                "model": model_for_stream,
                "choices": [{
                    "index": 0,
                    "delta": { "role": "assistant", "content": chunk },
                    "finish_reason": null,
                }],
            });
            yield Ok::<_, std::io::Error>(format!("data: {event}\n\n"));
        }
        let done = json!({
            "id": id_for_stream,
            "object": "chat.completion.chunk",
            "created": now_secs(),
            "model": model_for_stream,
            "choices": [{ "index": 0, "delta": {}, "finish_reason": "stop" }],
        });
        yield Ok(format!("data: {done}\n\n"));
        yield Ok("data: [DONE]\n\n".to_string());
    };

    let body = Body::from_stream(body_stream);
    Response::builder()
        .status(StatusCode::OK)
        .header("content-type", "text/event-stream")
        .header("cache-control", "no-cache")
        .body(body)
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)
}
