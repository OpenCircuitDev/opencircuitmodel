//! Mesh transport layer (v2+).
//!
//! Per spec v0.4 row 8: iroh primary + libp2p escape hatch via libp2p-iroh
//! bridge. This crate defines the transport-agnostic trait that the daemon
//! will program against, plus stub implementations for both backends.
//!
//! **Status:** v2 scaffold. The trait interface is final; the implementations
//! are stubs that return `not yet implemented` errors. Real iroh wiring lands
//! in v2 ("Two-Node Mesh"); the bench sandbox at
//! `bench/isolation/mesh-transport/multipass-fleet/` will activate against
//! this trait once v2 ships.
//!
//! Why scaffold now: the daemon's AppState doesn't yet hold a `MeshTransport`,
//! but committing the trait interface early means v2 doesn't have to refactor
//! consumer call sites — they can already program against `Arc<dyn MeshTransport>`.

use async_trait::async_trait;
use serde::{Deserialize, Serialize};
use std::time::Duration;

pub mod iroh_transport;
pub mod libp2p_transport;

/// Stable identifier for a peer on the OCM mesh. v2 will resolve this against
/// iroh's NodeAddr or libp2p's PeerId; for now, it's an opaque string.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct PeerId(pub String);

impl PeerId {
    pub fn new(s: impl Into<String>) -> Self {
        Self(s.into())
    }
}

impl std::fmt::Display for PeerId {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(&self.0)
    }
}

/// A peer record returned by discovery. Includes the peer's id plus a
/// recently-observed address (multiaddr-style for libp2p, NodeAddr for iroh —
/// here a plain string the implementation interprets).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PeerRecord {
    pub id: PeerId,
    pub address: String,
    pub last_seen_unix: u64,
}

/// Mesh-layer error type. Implementations map their native errors here.
#[derive(Debug, thiserror::Error)]
pub enum MeshError {
    #[error("not yet implemented: {0}")]
    NotYetImplemented(&'static str),
    #[error("transport error: {0}")]
    Transport(String),
    #[error("peer not found: {0}")]
    PeerNotFound(PeerId),
    #[error("timeout after {0:?}")]
    Timeout(Duration),
}

/// Transport-agnostic mesh interface. v2 will implement this for iroh first,
/// then libp2p as escape hatch.
#[async_trait]
pub trait MeshTransport: Send + Sync {
    /// Human-readable backend name ("iroh" / "libp2p" / "stub").
    fn name(&self) -> &'static str;

    /// This node's stable identity. Persisted across restarts so peers
    /// can recognize us across reconnects.
    fn local_peer_id(&self) -> PeerId;

    /// Bring the transport up — bind sockets, dial bootstrap nodes, start
    /// the discovery loop. Idempotent (safe to call twice).
    async fn start(&self) -> Result<(), MeshError>;

    /// Stop the transport gracefully.
    async fn stop(&self) -> Result<(), MeshError>;

    /// Currently-known peers. Snapshot — implementation decides freshness.
    async fn peers(&self) -> Result<Vec<PeerRecord>, MeshError>;

    /// Send raw bytes to a specific peer. v2 layers higher-level protocols
    /// (chat-relay, palace-gossip, skill-fetch) on top of this primitive.
    async fn send_to(&self, peer: &PeerId, payload: &[u8]) -> Result<(), MeshError>;
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn peer_id_round_trip() {
        let p = PeerId::new("12D3KooW…");
        assert_eq!(p.to_string(), "12D3KooW…");
    }

    #[tokio::test]
    async fn stub_transports_compile_against_trait() {
        // Ensure both stubs satisfy the trait. Compile check — runtime calls
        // are exercised in their respective module tests.
        let _iroh: std::sync::Arc<dyn MeshTransport> =
            std::sync::Arc::new(iroh_transport::IrohTransport::stub());
        let _libp2p: std::sync::Arc<dyn MeshTransport> =
            std::sync::Arc::new(libp2p_transport::Libp2pTransport::stub());
    }
}
