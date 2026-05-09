//! Localhost-only middleware. Rejects any request that didn't originate from
//! 127.0.0.1 / ::1. The OCM daemon is single-tenant local-first by default;
//! mesh exposure is a separate v2+ concern handled at the libp2p / iroh layer.

use axum::extract::{ConnectInfo, Request};
use axum::http::StatusCode;
use axum::middleware::Next;
use axum::response::Response;
use std::net::SocketAddr;

pub async fn require_localhost(
    ConnectInfo(addr): ConnectInfo<SocketAddr>,
    req: Request,
    next: Next,
) -> Result<Response, StatusCode> {
    if !addr.ip().is_loopback() {
        tracing::warn!(remote = %addr, "rejected non-loopback request");
        return Err(StatusCode::FORBIDDEN);
    }
    Ok(next.run(req).await)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::net::{IpAddr, Ipv4Addr, Ipv6Addr};

    #[test]
    fn loopback_ipv4_passes() {
        let addr: SocketAddr = SocketAddr::new(IpAddr::V4(Ipv4Addr::LOCALHOST), 12345);
        assert!(addr.ip().is_loopback());
    }

    #[test]
    fn loopback_ipv6_passes() {
        let addr: SocketAddr = SocketAddr::new(IpAddr::V6(Ipv6Addr::LOCALHOST), 12345);
        assert!(addr.ip().is_loopback());
    }

    #[test]
    fn external_ipv4_rejected() {
        let addr: SocketAddr = SocketAddr::new(IpAddr::V4(Ipv4Addr::new(8, 8, 8, 8)), 12345);
        assert!(!addr.ip().is_loopback());
    }
}
