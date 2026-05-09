//! iroh-backed mesh transport (v2 primary).
//!
//! Per spec v0.4 row 8: iroh's QUIC-native traversal hits ~90% residential
//! NAT success vs libp2p's measured 70% (4.4M attempts). The 20-percentage-point
//! delta is the most important variable in mesh viability.
//!
//! v2 implementation will use:
//! - `iroh::Endpoint` for QUIC connections
//! - `iroh::NodeId` for peer identity (mapped to our PeerId)
//! - `iroh-net::dns` for discovery
//! - `iroh-relay` fallback when direct connect fails
//!
//! Currently a stub: methods return MeshError::NotYetImplemented. This keeps
//! the trait surface stable so v2 can flip the implementation without changing
//! consumer call sites.

use crate::{MeshError, MeshTransport, PeerId, PeerRecord};
use async_trait::async_trait;

pub struct IrohTransport {
    local_peer_id: PeerId,
}

impl IrohTransport {
    /// Stub constructor — assigns a placeholder peer id. v2 replaces this
    /// with iroh's `SecretKey::generate()` -> derive NodeId -> persist.
    pub fn stub() -> Self {
        Self {
            local_peer_id: PeerId::new("iroh-stub-peer-id"),
        }
    }
}

#[async_trait]
impl MeshTransport for IrohTransport {
    fn name(&self) -> &'static str {
        "iroh"
    }

    fn local_peer_id(&self) -> PeerId {
        self.local_peer_id.clone()
    }

    async fn start(&self) -> Result<(), MeshError> {
        Err(MeshError::NotYetImplemented("iroh transport — v2"))
    }

    async fn stop(&self) -> Result<(), MeshError> {
        Err(MeshError::NotYetImplemented("iroh transport — v2"))
    }

    async fn peers(&self) -> Result<Vec<PeerRecord>, MeshError> {
        Err(MeshError::NotYetImplemented("iroh transport — v2"))
    }

    async fn send_to(&self, _peer: &PeerId, _payload: &[u8]) -> Result<(), MeshError> {
        Err(MeshError::NotYetImplemented("iroh transport — v2"))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn stub_returns_not_yet_implemented() {
        let t = IrohTransport::stub();
        assert_eq!(t.name(), "iroh");
        let result = t.start().await;
        assert!(matches!(result, Err(MeshError::NotYetImplemented(_))));
    }

    #[tokio::test]
    async fn stub_send_returns_not_yet_implemented() {
        let t = IrohTransport::stub();
        let peer = PeerId::new("anyone");
        let result = t.send_to(&peer, b"hello").await;
        assert!(matches!(result, Err(MeshError::NotYetImplemented(_))));
    }
}
