// Tauri runtime detection + invoke wrapper.
//
// In Tauri prod, `window.__TAURI_INTERNALS__` is injected by the runtime.
// In `npm run dev` (Vite alone), it's absent — so we need to gate Tauri-only
// features and surface a friendly fallback.

import { invoke as tauriInvoke } from '@tauri-apps/api/core';

export function isTauri(): boolean {
	return typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window;
}

/**
 * Invoke a Tauri command with a clear error if we're not running inside Tauri.
 * Most callers should check `isTauri()` first and render a fallback UI; this
 * wrapper exists so the same call site works for both dev (where it throws
 * a structured error) and prod (where it succeeds).
 */
export async function invoke<T>(cmd: string, args?: Record<string, unknown>): Promise<T> {
	if (!isTauri()) {
		throw new Error(`Tauri command '${cmd}' unavailable: not running inside Tauri runtime`);
	}
	return tauriInvoke<T>(cmd, args);
}
