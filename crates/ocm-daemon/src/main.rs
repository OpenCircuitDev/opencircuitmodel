#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod bootstrap;
mod commands;
mod paths;
mod settings;
mod supervisor;
mod tray;

use std::sync::{Arc, Mutex};
use tauri::tray::TrayIconBuilder;
use tauri::Manager;
use tracing::info;
use tracing_subscriber::EnvFilter;

fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(EnvFilter::from_default_env().add_directive("ocm=info".parse()?))
        .init();

    info!("OCM daemon starting");

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .invoke_handler(tauri::generate_handler![
            commands::get_settings,
            commands::save_settings,
            commands::list_registry_models,
            commands::download_model_cmd,
            commands::get_supervisor_status,
        ])
        .setup(|app| {
            let app_paths = paths::AppPaths::resolve()?;
            app_paths.ensure_all_exist()?;
            info!(
                config = %app_paths.config_dir.display(),
                data = %app_paths.data_dir.display(),
                "app paths resolved"
            );
            let settings_path = app_paths.config_dir.join("settings.toml");
            let loaded_settings = settings::Settings::load_or_default(&settings_path)?;
            info!(
                model = ?loaded_settings.model_id,
                port = loaded_settings.api_port,
                "settings loaded"
            );

            // Build the llama-server supervisor before bootstrap, so the
            // existing dependency probe sees the spawned process as up.
            // None means "supervision disabled this run" — preserves
            // pre-v0.1.2 behavior when the user doesn't opt in.
            let supervisor_state =
                match bootstrap::build_llama_supervisor(&loaded_settings, &app_paths.models_dir) {
                    Some((supervised, policy)) => {
                        let status = Arc::new(Mutex::new(supervisor::SupervisorStatus::default()));
                        let (shutdown_tx, shutdown_rx) = tokio::sync::watch::channel(false);
                        let status_for_loop = status.clone();
                        info!(
                            name = supervised.name(),
                            health_url = %policy.health_url,
                            "starting llama-server supervisor"
                        );
                        tauri::async_runtime::spawn(async move {
                            supervisor::supervise(supervised, policy, status_for_loop, shutdown_rx)
                                .await;
                        });
                        bootstrap::LlamaSupervisorState::live(status, shutdown_tx)
                    }
                    None => {
                        info!("llama-server supervisor not configured for this run");
                        bootstrap::LlamaSupervisorState::not_spawning()
                    }
                };

            // Spawn the bootstrap task — probes external dependencies and
            // starts the OCM HTTP API server in the background. Tauri's
            // setup() is sync so we hand off to a tokio task; the Tauri main
            // event loop continues independently. Note: bootstrap captures
            // settings by value at startup; live settings changes via the
            // save_settings command don't take effect until daemon restart
            // (the frontend surfaces this caveat in the settings panel).
            let settings_for_bootstrap = loaded_settings.clone();
            tauri::async_runtime::spawn(async move {
                bootstrap::bootstrap(settings_for_bootstrap).await;
            });

            let settings_state = commands::SettingsState {
                current: Mutex::new(loaded_settings),
                path: settings_path,
            };

            app.manage(app_paths);
            app.manage(settings_state);
            app.manage(supervisor_state);

            let menu = tray::build_tray_menu(app.handle())?;
            let _tray = TrayIconBuilder::new()
                .menu(&menu)
                .show_menu_on_left_click(true)
                .on_menu_event(|app, event| match event.id.as_ref() {
                    "show" => {
                        if let Some(w) = app.get_webview_window("main") {
                            let _ = w.show();
                            let _ = w.set_focus();
                        }
                    }
                    "quit" => {
                        info!("quit requested via tray");
                        app.exit(0);
                    }
                    _ => {}
                })
                .build(app)?;
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("Tauri runtime failed");

    Ok(())
}
