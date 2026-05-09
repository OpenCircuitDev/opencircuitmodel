// Model registry — bundled into the daemon binary, exposed both over HTTP
// (GET /v1/registry/models) and as a Tauri command (list_registry_models).
// We use HTTP for listing (works in dev mode) and Tauri commands for
// downloads (need filesystem access).

import { invoke } from './tauri';

export interface ModelEntry {
	id: string;
	display_name: string;
	size_mb: number;
	min_ram_gb: number;
	url: string;
	sha256: string;
	tier: string;
}

export interface Registry {
	version: number;
	models: ModelEntry[];
}

export async function listRegistryModels(): Promise<Registry> {
	const r = await fetch(`/v1/registry/models`);
	if (!r.ok) {
		throw new Error(`registry endpoint returned ${r.status}: ${await r.text()}`);
	}
	return (await r.json()) as Registry;
}

export async function downloadModel(modelId: string): Promise<string> {
	return invoke<string>('download_model_cmd', { modelId });
}
