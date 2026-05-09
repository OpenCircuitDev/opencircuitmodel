//! Integration smoke test for ocm-memory against a running Mem0 OpenMemory server.
//!
//! Skipped by default. Run with:
//!   OCM_MEM0_URL=http://localhost:8765 OCM_MEM0_USER=ocm-test \
//!     cargo test -p ocm-memory --test mem0_smoke -- --ignored --nocapture
//!
//! Pre-req: a Mem0 OpenMemory server running locally. See:
//!   https://mem0.ai/blog/introducing-openmemory-mcp

use ocm_memory::Mem0Client;

#[tokio::test]
#[ignore]
async fn add_then_search_round_trip() {
    let url = std::env::var("OCM_MEM0_URL").expect("OCM_MEM0_URL");
    let user = std::env::var("OCM_MEM0_USER").unwrap_or_else(|_| "ocm-smoke".into());
    let client = Mem0Client::new(url, user);

    client.health().await.expect("Mem0 health");

    // Add a memory
    let id = client
        .add(
            "OCM canonical model is Qwen3-30B-A3B MoE per spec v0.4 row 16",
            None,
        )
        .await
        .expect("add memory");

    // Search for it
    let results = client
        .search("what is the canonical model for OCM", 5)
        .await
        .expect("search");

    assert!(!results.is_empty(), "expected at least one search result");
    // Top result should reference what we just added
    let top = &results[0];
    assert!(
        top.memory.text.contains("Qwen") || top.memory.id == id,
        "top result should match the added memory: {top:?}"
    );
}
