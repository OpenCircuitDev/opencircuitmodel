#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod paths;
mod settings;
mod tray;

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
            app.manage(app_paths);
            app.manage(loaded_settings);

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
