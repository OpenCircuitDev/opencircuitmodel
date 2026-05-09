<script lang="ts">
	import { onMount } from 'svelte';
	import { getSettings, saveSettings, type Settings, type Theme } from '$lib/settings';
	import { isTauri } from '$lib/tauri';

	let inTauri = $state(false);
	let loading = $state(true);
	let saving = $state(false);
	let saved = $state(false);
	let loadError = $state<string | null>(null);
	let saveError = $state<string | null>(null);
	let settings = $state<Settings | null>(null);

	onMount(async () => {
		inTauri = isTauri();
		if (!inTauri) {
			loading = false;
			return;
		}
		try {
			settings = await getSettings();
		} catch (e) {
			loadError = e instanceof Error ? e.message : String(e);
		} finally {
			loading = false;
		}
	});

	async function onSubmit(e: Event) {
		e.preventDefault();
		if (!settings) return;
		saving = true;
		saved = false;
		saveError = null;
		try {
			await saveSettings(settings);
			saved = true;
			setTimeout(() => {
				saved = false;
			}, 3000);
		} catch (e) {
			saveError = e instanceof Error ? e.message : String(e);
		} finally {
			saving = false;
		}
	}

	const themeOptions: Theme[] = ['system', 'dark', 'light'];
</script>

<div class="flex h-full flex-col">
	<div class="border-b border-ocm-border bg-ocm-surface px-4 py-2">
		<h1 class="font-mono text-sm">Settings</h1>
	</div>

	<div class="flex-1 overflow-y-auto px-6 py-6">
		{#if !inTauri && !loading}
			<div class="rounded border border-ocm-border bg-ocm-surface p-4 text-sm text-ocm-muted">
				Settings management requires the Tauri build of OCM. Run <code
					class="rounded bg-ocm-bg px-1 font-mono text-xs">cargo tauri dev</code
				>
				from the daemon crate, or install the packaged OCM app, to manage settings here. Until then,
				edit <code class="rounded bg-ocm-bg px-1 font-mono text-xs">settings.toml</code> in
				your OS config dir directly.
			</div>
		{:else if loading}
			<div class="text-sm text-ocm-muted">loading settings…</div>
		{:else if loadError}
			<div
				class="rounded border border-rose-700 bg-rose-950 px-3 py-2 font-mono text-xs text-rose-200"
			>
				failed to load: {loadError}
			</div>
		{:else if settings}
			<form
				onsubmit={onSubmit}
				class="grid max-w-2xl grid-cols-[10rem_1fr] items-center gap-x-4 gap-y-3 text-sm"
			>
				<label for="model_id" class="text-ocm-muted">model id</label>
				<input
					id="model_id"
					type="text"
					placeholder="(use default)"
					class="rounded border border-ocm-border bg-ocm-bg px-2 py-1 font-mono"
					bind:value={settings.model_id}
				/>

				<label for="api_port" class="text-ocm-muted">API port</label>
				<input
					id="api_port"
					type="number"
					min="1024"
					max="65535"
					class="w-32 rounded border border-ocm-border bg-ocm-bg px-2 py-1 font-mono"
					bind:value={settings.api_port}
				/>

				<label for="mcp_enabled" class="text-ocm-muted">MCP server</label>
				<label class="flex items-center gap-2">
					<input id="mcp_enabled" type="checkbox" bind:checked={settings.mcp_enabled} />
					<span class="text-xs text-ocm-muted">expose ocm-mcp via stdio</span>
				</label>

				<label for="theme" class="text-ocm-muted">theme</label>
				<select
					id="theme"
					class="w-32 rounded border border-ocm-border bg-ocm-bg px-2 py-1 font-mono"
					bind:value={settings.theme}
				>
					{#each themeOptions as t (t)}
						<option value={t}>{t}</option>
					{/each}
				</select>

				<label for="inference_url" class="text-ocm-muted">inference URL</label>
				<input
					id="inference_url"
					type="text"
					placeholder="http://127.0.0.1:8080"
					class="rounded border border-ocm-border bg-ocm-bg px-2 py-1 font-mono"
					bind:value={settings.inference_base_url}
				/>

				<label for="mem0_url" class="text-ocm-muted">Mem0 URL</label>
				<input
					id="mem0_url"
					type="text"
					placeholder="http://127.0.0.1:8765"
					class="rounded border border-ocm-border bg-ocm-bg px-2 py-1 font-mono"
					bind:value={settings.mem0_base_url}
				/>

				<label for="topk" class="text-ocm-muted">retrieval top_k</label>
				<input
					id="topk"
					type="number"
					min="0"
					max="50"
					placeholder="(default 5)"
					class="w-32 rounded border border-ocm-border bg-ocm-bg px-2 py-1 font-mono"
					bind:value={settings.retrieval_top_k}
				/>

				<div class="col-span-2 flex items-center gap-3 pt-3">
					<button
						type="submit"
						class="rounded border border-ocm-accent-dim bg-ocm-accent-dim px-4 py-1.5 text-sm text-ocm-bg disabled:opacity-30"
						disabled={saving}
					>
						{saving ? 'saving…' : 'save'}
					</button>
					{#if saved}
						<span class="text-xs text-ocm-accent">saved · restart daemon to apply</span>
					{/if}
					{#if saveError}
						<span class="font-mono text-xs text-rose-400">save failed: {saveError}</span>
					{/if}
				</div>

				<div
					class="col-span-2 mt-3 rounded border border-ocm-border bg-ocm-surface px-3 py-2 text-xs text-ocm-muted"
				>
					Most fields take effect on daemon restart (model, ports, URLs, retrieval depth).
					Theme applies immediately.
				</div>
			</form>
		{/if}
	</div>
</div>
