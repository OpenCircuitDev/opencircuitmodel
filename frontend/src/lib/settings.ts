// Settings types — mirror crates/ocm-daemon/src/settings.rs.
// Source of truth lives on the Rust side; if you add a field there, add it here.

export type Theme = 'dark' | 'light' | 'system';

// Mirror of crate::settings::Backend (serde lowercase). `auto` preserves
// platform-detect (the pre-v0.1.1 default). `ollama` is the zero-extra-process
// path — point OCM at an already-running Ollama daemon.
export type Backend = 'auto' | 'llamacpp' | 'vllm' | 'ollama';

export interface Settings {
	model_id: string | null;
	api_port: number;
	mcp_enabled: boolean;
	theme: Theme;
	inference_base_url: string | null;
	mem0_base_url: string | null;
	retrieval_top_k: number | null;
	backend: Backend;
	ollama_base_url: string | null;
	ollama_model: string | null;
}

import { invoke } from './tauri';

export async function getSettings(): Promise<Settings> {
	return invoke<Settings>('get_settings');
}

export async function saveSettings(settings: Settings): Promise<void> {
	return invoke<void>('save_settings', { newSettings: settings });
}
