use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};
use std::path::Path;

#[derive(Debug, Serialize, Deserialize, Clone, PartialEq)]
pub struct Settings {
    pub model_id: Option<String>,
    pub api_port: u16,
    pub mcp_enabled: bool,
    pub theme: Theme,
    /// Override the default inference backend URL (default: http://127.0.0.1:8080).
    /// Set to a vLLM URL (typically http://127.0.0.1:8000) on NVIDIA hosts.
    #[serde(default)]
    pub inference_base_url: Option<String>,
    /// Override the default Mem0 OpenMemory MCP URL (default: http://127.0.0.1:8765).
    #[serde(default)]
    pub mem0_base_url: Option<String>,
    /// Number of memories to retrieve per chat turn. Default 5. Set to 0 to disable.
    #[serde(default)]
    pub retrieval_top_k: Option<u32>,
    /// Which inference backend to use. `Auto` (default) preserves pre-v0.1.1
    /// behavior: platform-detect picks llama.cpp on Mac/Windows/CPU-Linux and
    /// vLLM on CUDA Linux. Explicit `LlamaCpp` / `Vllm` / `Ollama` override
    /// detection — the Ollama branch is the "I have an Ollama daemon already,
    /// point OCM at it" zero-extra-process path.
    #[serde(default)]
    pub backend: Backend,
    /// Override the Ollama daemon URL. Only consulted when `backend = "ollama"`.
    /// Default (when unset) is `http://127.0.0.1:11434` — Ollama's installed default.
    #[serde(default)]
    pub ollama_base_url: Option<String>,
    /// Ollama model tag (e.g. `llama3`, `qwen2.5:7b`). REQUIRED by the Ollama
    /// native API — there is no server-side default. When unset, bootstrap
    /// falls back to `ocm_inference::ollama::DEFAULT_MODEL`.
    #[serde(default)]
    pub ollama_model: Option<String>,
}

#[derive(Debug, Serialize, Deserialize, Clone, PartialEq, Copy)]
#[serde(rename_all = "lowercase")]
pub enum Theme {
    Dark,
    Light,
    System,
}

/// Inference backend selection. Wire-format is lowercase TOML (`backend = "ollama"`).
#[derive(Debug, Serialize, Deserialize, Clone, PartialEq, Eq, Copy, Default)]
#[serde(rename_all = "lowercase")]
pub enum Backend {
    /// Platform-detect (existing pre-v0.1.1 behavior).
    #[default]
    Auto,
    LlamaCpp,
    Vllm,
    Ollama,
}

impl Default for Settings {
    fn default() -> Self {
        Self {
            model_id: None,
            api_port: 7300,
            mcp_enabled: true,
            theme: Theme::System,
            inference_base_url: None,
            mem0_base_url: None,
            retrieval_top_k: None,
            backend: Backend::Auto,
            ollama_base_url: None,
            ollama_model: None,
        }
    }
}

impl Settings {
    pub fn load_or_default(path: &Path) -> Result<Self> {
        if !path.exists() {
            return Ok(Self::default());
        }
        let raw = std::fs::read_to_string(path).context("read settings.toml")?;
        toml::from_str(&raw).context("parse settings.toml")
    }

    /// Persist settings to disk. Currently called only from tests; will be
    /// invoked by Tauri command handlers in Phase 5 when the settings UI lands.
    #[allow(dead_code)]
    pub fn save(&self, path: &Path) -> Result<()> {
        let raw = toml::to_string_pretty(self).context("serialize settings")?;
        std::fs::write(path, raw).context("write settings.toml")?;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    #[test]
    fn round_trip_default_settings() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("settings.toml");
        let original = Settings::default();
        original.save(&path).unwrap();
        let loaded = Settings::load_or_default(&path).unwrap();
        assert_eq!(original, loaded);
    }

    #[test]
    fn missing_file_yields_default() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("nonexistent.toml");
        let s = Settings::load_or_default(&path).unwrap();
        assert_eq!(s, Settings::default());
    }

    #[test]
    fn default_backend_is_auto() {
        // Auto preserves the platform-detect behavior that shipped before this
        // field existed; explicit selection (LlamaCpp / Vllm / Ollama) is opt-in.
        let s = Settings::default();
        assert_eq!(s.backend, Backend::Auto);
        assert_eq!(s.ollama_base_url, None);
        assert_eq!(s.ollama_model, None);
    }

    #[test]
    fn backend_serializes_lowercase() {
        // TOML keys are lowercase by convention; matches Theme's serde shape.
        let raw = toml::to_string(&Settings {
            backend: Backend::Ollama,
            ..Settings::default()
        })
        .unwrap();
        assert!(raw.contains("backend = \"ollama\""));
    }

    #[test]
    fn ollama_settings_round_trip_via_toml() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("settings.toml");
        let original = Settings {
            backend: Backend::Ollama,
            ollama_base_url: Some("http://127.0.0.1:11434".into()),
            ollama_model: Some("llama3".into()),
            ..Settings::default()
        };
        original.save(&path).unwrap();
        let loaded = Settings::load_or_default(&path).unwrap();
        assert_eq!(loaded, original);
        assert_eq!(loaded.backend, Backend::Ollama);
        assert_eq!(
            loaded.ollama_base_url.as_deref(),
            Some("http://127.0.0.1:11434")
        );
        assert_eq!(loaded.ollama_model.as_deref(), Some("llama3"));
    }

    #[test]
    fn legacy_settings_toml_without_backend_field_still_parses() {
        // Forward-compat: users with a settings.toml written before v0.1.1
        // (no `backend` key) must still load — the new field defaults to Auto.
        let dir = tempdir().unwrap();
        let path = dir.path().join("settings.toml");
        let legacy = r#"
api_port = 7300
mcp_enabled = true
theme = "system"
"#;
        std::fs::write(&path, legacy).unwrap();
        let loaded = Settings::load_or_default(&path).unwrap();
        assert_eq!(loaded.backend, Backend::Auto);
        assert_eq!(loaded.ollama_base_url, None);
        assert_eq!(loaded.ollama_model, None);
    }

    #[test]
    fn all_backend_variants_round_trip() {
        for kind in [
            Backend::Auto,
            Backend::LlamaCpp,
            Backend::Vllm,
            Backend::Ollama,
        ] {
            let s = Settings {
                backend: kind,
                ..Settings::default()
            };
            let raw = toml::to_string(&s).unwrap();
            let back: Settings = toml::from_str(&raw).unwrap();
            assert_eq!(back.backend, kind, "round-trip failed for {kind:?}");
        }
    }
}
