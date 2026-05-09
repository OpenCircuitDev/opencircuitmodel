//! libp2p-backed mesh transport (v2 escape hatch).
//!
//! Per spec v0.4 row 8: libp2p as escape hatch via libp2p-iroh bridge —
//! single-vendor risk on iroh is mitigated by keeping app protocols
//! transport-agnostic, so libp2p remains a viable fallback if iroh's
//! trajectory ever changes.
//!
//! v2 implementation will likely use:
//! - `libp2p::Swarm` with TCP + WebSocket transports
//! - `libp2p-mdns` for LAN discovery
//! - `libp2p-kad` for DHT-based discovery (with the libp2p public bootnodes)
//! - `libp2p-relay` for circuit-relay fallback
//!
//! Currently a stub like the iroh side.

use crate::{MeshError, MeshTransport, PeerId, PeerRecord};
use async_trait::async_trait;

pub struct Libp2pTransport {
    local_peer_id: PeerId,
}

impl Libp2pTransport {
    pub fn stub() -> Self {
        Self {
            local_peer_id: PeerId::new("libp2p-stub-peer-id"),
        }
    }
}

#[async_trait]
impl MeshTransport for Libp2pTransport {
    fn name(&self) -> &'static str {
        "libp2p"
    }

    fn local_peer_id(&self) -> PeerId {
        self.local_peer_id.clone()
    }

    async fn start(&self) -> Result<(), MeshError> {
        Err(MeshError::NotYetImplemented("libp2p transport — v2"))
    }

    async fn stop(&self) -> Result<(), MeshError> {
        Err(MeshError::NotYetImplemented("libp2p transport — v2"))
    }

    async fn peers(&self) -> Result<Vec<PeerRecord>, MeshError> {
        Err(MeshError::NotYetImplemented("libp2p transport — v2"))
    }

    async fn send_to(&self, _peer: &PeerId, _payload: &[u8]) -> Result<(), MeshError> {
        Err(MeshError::NotYetImplemented("libp2p transport — v2"))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn stub_returns_not_yet_implemented() {
        let t = Libp2pTransport::stub();
        assert_eq!(t.name(), "libp2p");
        let result = t.peers().await;
        assert!(matches!(result, Err(MeshError::NotYetImplemented(_))));
    }
}
