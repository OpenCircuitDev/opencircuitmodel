//! Curated model registry + SHA256-verified downloader.
//!
//! `registry.json` is bundled at compile time via `include_str!`. To add a
//! model, add an entry to registry.json with the upstream URL and the SHA256
//! computed once via `shasum -a 256 <file>`. Empty sha256 means "not yet
//! verified" — the downloader refuses these so we never ship unverified bits.

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct Registry {
    pub version: u32,
    pub models: Vec<ModelEntry>,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct ModelEntry {
    pub id: String,
    pub display_name: String,
    pub size_mb: u64,
    pub min_ram_gb: u32,
    pub url: String,
    /// Lowercase hex SHA256. Empty string means "not yet recorded"; the
    /// downloader refuses these entries so the user is never given an
    /// unverified GGUF.
    pub sha256: String,
    /// "tiny" | "default" | "canonical" — used by the UI to group + sort.
    /// Defaults to "default" if missing for forward-compat with v0 registries.
    #[serde(default = "default_tier")]
    pub tier: String,
}

fn default_tier() -> String {
    "default".to_string()
}

impl ModelEntry {
    /// Returns true if the entry has a recorded SHA256 (not empty).
    /// The downloader uses this as a guard before initiating any network IO.
    pub fn is_verifiable(&self) -> bool {
        !self.sha256.is_empty() && self.sha256.chars().all(|c| c.is_ascii_hexdigit())
    }
}

impl Registry {
    /// Load the registry that was bundled into the binary at compile time.
    pub fn load_bundled() -> anyhow::Result<Self> {
        const BUNDLED: &str = include_str!("../registry.json");
        Ok(serde_json::from_str(BUNDLED)?)
    }

    pub fn find(&self, id: &str) -> Option<&ModelEntry> {
        self.models.iter().find(|m| m.id == id)
    }

    pub fn by_tier<'a>(&'a self, tier: &'a str) -> impl Iterator<Item = &'a ModelEntry> {
        self.models.iter().filter(move |m| m.tier == tier)
    }
}

pub mod downloader;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn bundled_registry_parses() {
        let r = Registry::load_bundled().expect("bundled registry parses");
        assert_eq!(r.version, 1);
        assert!(!r.models.is_empty());
        for m in &r.models {
            assert!(!m.id.is_empty(), "every entry has a non-empty id");
            assert!(!m.url.is_empty(), "every entry has a non-empty url");
            assert!(m.size_mb > 0, "every entry has a positive size");
            assert!(!m.tier.is_empty(), "every entry has a tier");
        }
    }

    #[test]
    fn find_by_id_returns_some_when_present() {
        let r = Registry::load_bundled().unwrap();
        let known = &r.models[0].id.clone();
        assert!(r.find(known).is_some());
        assert!(r.find("does-not-exist-anywhere").is_none());
    }

    #[test]
    fn by_tier_filters_correctly() {
        let r = Registry::load_bundled().unwrap();
        let tiny: Vec<_> = r.by_tier("tiny").collect();
        // Don't hard-code the count — registry will grow over time. Just
        // assert that tier-filtering returns a coherent subset.
        for m in &tiny {
            assert_eq!(m.tier, "tiny");
        }
    }

    #[test]
    fn is_verifiable_requires_hex_sha256() {
        let mut entry = ModelEntry {
            id: "test".into(),
            display_name: "test".into(),
            size_mb: 100,
            min_ram_gb: 4,
            url: "https://example/x.gguf".into(),
            sha256: "".into(),
            tier: "default".into(),
        };
        assert!(!entry.is_verifiable(), "empty hash is not verifiable");

        entry.sha256 = "not_hex".into();
        assert!(!entry.is_verifiable(), "non-hex hash is not verifiable");

        entry.sha256 = "deadbeef".into();
        assert!(entry.is_verifiable(), "hex hash is verifiable");
    }
}
