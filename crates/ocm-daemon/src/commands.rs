//! Tauri commands invoked from the SvelteKit frontend.
//!
//! Settings management is the v1 surface. HTTP-based settings API was
//! considered (would have worked in `npm run dev` without Tauri) but
//! Tauri commands won out: settings are inherently a desktop-app local
//! concern, and Tauri commands need no auth (process-local) where HTTP
//! would need defense-in-depth even on localhost.
//!
//! Settings changes are persisted to settings.toml immediately. Most
//! fields are *read at daemon startup* and don't take effect until the
//! daemon restarts — `model_id`, `inference_base_url`, `mem0_base_url`,
//! `retrieval_top_k`, `api_port`, `mcp_enabled`. The frontend surfaces
//! "restart required to apply" so the user isn't surprised.

use crate::paths::AppPaths;
use crate::settings::Settings;
use ocm_models::{downloader::download_model, Registry};
use std::path::PathBuf;
use std::sync::Mutex;
use tauri::State;

/// Tauri-managed handle to the live settings + their on-disk location.
pub struct SettingsState {
    pub current: Mutex<Settings>,
    pub path: PathBuf,
}

#[tauri::command]
pub fn get_settings(state: State<'_, SettingsState>) -> Result<Settings, String> {
    state
        .current
        .lock()
        .map(|s| s.clone())
        .map_err(|e| format!("settings state poisoned: {e}"))
}

#[tauri::command]
pub fn save_settings(
    new_settings: Settings,
    state: State<'_, SettingsState>,
) -> Result<(), String> {
    let mut current = state
        .current
        .lock()
        .map_err(|e| format!("settings state poisoned: {e}"))?;
    new_settings
        .save(&state.path)
        .map_err(|e| format!("write settings.toml: {e}"))?;
    *current = new_settings;
    tracing::info!(path = %state.path.display(), "settings saved");
    Ok(())
}

/// Read the bundled registry at request time. Cheap (KB-scale JSON parse).
/// The HTTP equivalent is GET /v1/registry/models — Tauri command exists for
/// frontends that prefer the in-process call over an HTTP roundtrip.
#[tauri::command]
pub fn list_registry_models() -> Result<Registry, String> {
    Registry::load_bundled().map_err(|e| format!("load bundled registry: {e}"))
}

/// Download a model by registry id into the app data dir under "models/".
/// Returns the absolute path on success. Refuses entries with empty sha256
/// (registry guards unverified weights).
#[tauri::command]
pub async fn download_model_cmd(
    model_id: String,
    paths: State<'_, AppPaths>,
) -> Result<String, String> {
    let registry = Registry::load_bundled().map_err(|e| format!("load registry: {e}"))?;
    let entry = registry
        .find(&model_id)
        .ok_or_else(|| format!("unknown model id: {model_id}"))?
        .clone();
    let dest_dir = paths.models_dir.clone();
    let path = download_model(&entry, &dest_dir, None)
        .await
        .map_err(|e| format!("download {model_id}: {e}"))?;
    Ok(path.display().to_string())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::settings::Theme;
    use tempfile::tempdir;

    fn settings_state_for_test() -> (SettingsState, PathBuf, tempfile::TempDir) {
        let dir = tempdir().unwrap();
        let path = dir.path().join("settings.toml");
        let initial = Settings::default();
        initial.save(&path).unwrap();
        let state = SettingsState {
            current: Mutex::new(initial),
            path: path.clone(),
        };
        (state, path, dir)
    }

    #[test]
    fn save_settings_persists_to_disk() {
        // Tauri commands take State<'_, T>, which we can't easily construct
        // outside Tauri's runtime. Test the underlying logic directly: load,
        // mutate, save, reload, assert.
        let (state, path, _dir) = settings_state_for_test();

        let mut updated = state.current.lock().unwrap().clone();
        updated.api_port = 17400;
        updated.theme = Theme::Dark;
        updated.retrieval_top_k = Some(7);
        updated.save(&path).unwrap();

        let reloaded = Settings::load_or_default(&path).unwrap();
        assert_eq!(reloaded.api_port, 17400);
        assert_eq!(reloaded.theme, Theme::Dark);
        assert_eq!(reloaded.retrieval_top_k, Some(7));
    }

    #[test]
    fn settings_state_holds_current_in_sync_with_disk() {
        let (state, path, _dir) = settings_state_for_test();

        // Mutate via the Mutex (simulates the inner half of save_settings)
        {
            let mut current = state.current.lock().unwrap();
            current.api_port = 17500;
            current.save(&path).unwrap();
        }

        // The state's current should now reflect the new value
        let snapshot = state.current.lock().unwrap().clone();
        assert_eq!(snapshot.api_port, 17500);

        // And the file on disk should match
        let from_disk = Settings::load_or_default(&path).unwrap();
        assert_eq!(from_disk.api_port, 17500);
    }
}
