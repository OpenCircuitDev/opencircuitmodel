//! OCM MCP server — bridges MCP stdio JSON-RPC to OCM daemon's HTTP API.
//!
//! Configure your MCP client (Claude Code, Cursor, Cline, Continue.dev, etc.)
//! to launch `ocm-mcp` as a subprocess. The OCM daemon must already be running
//! (typically on http://127.0.0.1:7300, configurable via OCM_API_URL env var).
//!
//! Per spec v0.4 row 11: OpenAI-compat HTTP + MCP server are both table-stakes
//! for v1. This binary completes the MCP half.

mod bridge;
mod dispatch;
mod protocol;

use bridge::OcmBridge;
use dispatch::dispatch;
use protocol::JsonRpcRequest;
use std::io::Write;
use tokio::io::{AsyncBufReadExt, BufReader};
use tracing::{error, info};

const DEFAULT_API_URL: &str = "http://127.0.0.1:7300";

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    // Logs to stderr so they don't pollute the JSON-RPC stream on stdout.
    tracing_subscriber::fmt()
        .with_writer(std::io::stderr)
        .with_env_filter(
            tracing_subscriber::EnvFilter::from_default_env()
                .add_directive("ocm_mcp=info".parse()?),
        )
        .init();

    let api_url = std::env::var("OCM_API_URL").unwrap_or_else(|_| DEFAULT_API_URL.to_string());
    info!(url = %api_url, "ocm-mcp starting; bridging stdio JSON-RPC -> OCM HTTP API");

    let bridge = OcmBridge::new(api_url);

    let stdin = tokio::io::stdin();
    let stdout = std::io::stdout();
    let mut reader = BufReader::new(stdin).lines();

    while let Some(line) = reader.next_line().await? {
        if line.trim().is_empty() {
            continue;
        }

        let req: JsonRpcRequest = match serde_json::from_str(&line) {
            Ok(r) => r,
            Err(e) => {
                error!(error = %e, "failed to parse JSON-RPC request; ignoring");
                continue;
            }
        };

        let response = dispatch(req, &bridge).await;

        if let Some(resp) = response {
            match serde_json::to_string(&resp) {
                Ok(text) => {
                    let mut out = stdout.lock();
                    if writeln!(out, "{text}").is_err() {
                        error!("failed to write response to stdout; client disconnected?");
                        break;
                    }
                    if out.flush().is_err() {
                        error!("failed to flush stdout");
                        break;
                    }
                }
                Err(e) => error!(error = %e, "failed to serialize response"),
            }
        }
    }

    info!("ocm-mcp exiting (stdin closed)");
    Ok(())
}
