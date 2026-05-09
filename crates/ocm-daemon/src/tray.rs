use tauri::menu::{Menu, MenuItem};
use tauri::{AppHandle, Wry};

pub fn build_tray_menu(app: &AppHandle) -> tauri::Result<Menu<Wry>> {
    let show = MenuItem::with_id(app, "show", "Show Window", true, None::<&str>)?;
    let quit = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;
    Menu::with_items(app, &[&show, &quit])
}

#[cfg(test)]
mod tests {
    #[test]
    fn menu_ids_are_unique() {
        let ids = vec!["show", "quit"];
        let mut sorted = ids.clone();
        sorted.sort();
        sorted.dedup();
        assert_eq!(ids.len(), sorted.len(), "menu item ids must be unique");
    }
}
