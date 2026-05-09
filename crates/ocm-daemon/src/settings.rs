use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};
use std::path::Path;

#[derive(Debug, Serialize, Deserialize, Clone, PartialEq)]
pub struct Settings {
    pub model_id: Option<String>,
    pub api_port: u16,
    pub mcp_enabled: bool,
    pub theme: Theme,
}

#[derive(Debug, Serialize, Deserialize, Clone, PartialEq, Copy)]
#[serde(rename_all = "lowercase")]
pub enum Theme {
    Dark,
    Light,
    System,
}

impl Default for Settings {
    fn default() -> Self {
        Self {
            model_id: None,
            api_port: 7300,
            mcp_enabled: true,
            theme: Theme::System,
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
}
