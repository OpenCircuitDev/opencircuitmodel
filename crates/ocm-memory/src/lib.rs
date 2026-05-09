//! Mem0 client for OCM — talks to a running Mem0 OpenMemory MCP server via REST.
//!
//! v0.4 spec decision row 9 locks Mem0 v3 + OpenMemory MCP as OCM v1's memory layer.
//! This crate provides a thin Rust client that the daemon uses to:
//! - check the Mem0 server's health
//! - add a memory (a piece of conversation, file, or curated knowledge)
//! - search memories by semantic query (library-driven retrieval per spec row 9)
//! - retrieve a specific memory by id
//!
//! The library-driven retrieval pattern is the *load-bearing* property that makes
//! Mem0 work with small (7-13B) open models: the agent does NOT decide when to
//! retrieve. The orchestrator (this crate's caller) calls `search` before the
//! model's turn and feeds the retrieved chunks as context. The model never has
//! to drive memory tooling, which is exactly the failure mode Letta's own
//! engineers admit happens with Llama 8B.
//!
//! Reference: https://mem0.ai/blog/mem0-the-token-efficient-memory-algorithm

pub mod client;
pub use client::{Mem0Client, Mem0Error, Memory, MemoryId, SearchResult};
