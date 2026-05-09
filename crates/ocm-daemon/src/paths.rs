use anyhow::{Context, Result};
use std::path::PathBuf;

pub struct AppPaths {
    pub config_dir: PathBuf,
    pub data_dir: PathBuf,
    pub models_dir: PathBuf,
    pub log_dir: PathBuf,
}

impl AppPaths {
    pub fn resolve() -> Result<Self> {
        let dirs = directories::ProjectDirs::from("org", "opencircuitmodel", "OCM")
            .context("could not resolve platform-specific app directories")?;
        let config_dir = dirs.config_dir().to_path_buf();
        let data_dir = dirs.data_dir().to_path_buf();
        let models_dir = data_dir.join("models");
        let log_dir = data_dir.join("logs");
        Ok(Self { config_dir, data_dir, models_dir, log_dir })
    }

    pub fn ensure_all_exist(&self) -> Result<()> {
        for d in [&self.config_dir, &self.data_dir, &self.models_dir, &self.log_dir] {
            std::fs::create_dir_all(d)
                .with_context(|| format!("could not create dir {}", d.display()))?;
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn resolves_distinct_dirs() {
        let p = AppPaths::resolve().expect("resolve paths");
        assert_ne!(p.config_dir, p.data_dir);
        assert!(p.models_dir.starts_with(&p.data_dir));
        assert!(p.log_dir.starts_with(&p.data_dir));
    }

    #[test]
    fn ensure_all_exist_is_idempotent() {
        let p = AppPaths::resolve().expect("resolve paths");
        p.ensure_all_exist().expect("first call");
        p.ensure_all_exist().expect("second call");
        assert!(p.config_dir.exists());
        assert!(p.data_dir.exists());
        assert!(p.models_dir.exists());
        assert!(p.log_dir.exists());
    }
}
