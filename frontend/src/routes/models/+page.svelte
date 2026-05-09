<script lang="ts">
	import { onMount } from 'svelte';
	import { listRegistryModels, downloadModel, type ModelEntry } from '$lib/registry';
	import { isTauri } from '$lib/tauri';

	let inTauri = $state(false);
	let loading = $state(true);
	let loadError = $state<string | null>(null);
	let models = $state<ModelEntry[]>([]);

	// Map model_id -> { state, message } for UI status
	type DownloadState = 'idle' | 'downloading' | 'done' | 'error';
	let downloads = $state<Record<string, { state: DownloadState; message?: string }>>({});

	onMount(async () => {
		inTauri = isTauri();
		try {
			const registry = await listRegistryModels();
			models = registry.models;
		} catch (e) {
			loadError = e instanceof Error ? e.message : String(e);
		} finally {
			loading = false;
		}
	});

	async function startDownload(model: ModelEntry) {
		if (!inTauri) return;
		downloads[model.id] = { state: 'downloading' };
		try {
			const path = await downloadModel(model.id);
			downloads[model.id] = { state: 'done', message: path };
		} catch (e) {
			downloads[model.id] = {
				state: 'error',
				message: e instanceof Error ? e.message : String(e)
			};
		}
	}

	function formatSize(mb: number): string {
		return mb >= 1024 ? `${(mb / 1024).toFixed(1)} GB` : `${mb} MB`;
	}

	function tierColor(tier: string): string {
		switch (tier) {
			case 'tiny':
				return 'text-emerald-400';
			case 'canonical':
				return 'text-fuchsia-400';
			default:
				return 'text-ocm-accent';
		}
	}
</script>

<div class="flex h-full flex-col">
	<div class="border-b border-ocm-border bg-ocm-surface px-4 py-2">
		<h1 class="font-mono text-sm">Models</h1>
	</div>

	<div class="flex-1 overflow-y-auto px-6 py-6">
		{#if loading}
			<div class="text-sm text-ocm-muted">loading registry…</div>
		{:else if loadError}
			<div
				class="rounded border border-rose-700 bg-rose-950 px-3 py-2 font-mono text-xs text-rose-200"
			>
				failed to load registry: {loadError}
			</div>
		{:else if models.length === 0}
			<div class="text-sm text-ocm-muted">registry is empty</div>
		{:else}
			{#if !inTauri}
				<div
					class="mb-4 rounded border border-ocm-border bg-ocm-surface px-3 py-2 text-xs text-ocm-muted"
				>
					Browsing only — model downloads require the Tauri build (filesystem access).
				</div>
			{/if}

			<div class="space-y-3">
				{#each models as m (m.id)}
					{@const status = downloads[m.id] ?? { state: 'idle' }}
					<div
						class="rounded border border-ocm-border bg-ocm-surface px-4 py-3 transition-colors"
					>
						<div class="flex items-baseline justify-between gap-4">
							<div class="flex-1">
								<div class="flex items-center gap-3">
									<span class="font-mono text-sm">{m.display_name}</span>
									<span class="font-mono text-[10px] uppercase {tierColor(m.tier)}">
										{m.tier}
									</span>
								</div>
								<div class="mt-1 flex items-center gap-3 text-xs text-ocm-muted">
									<span class="font-mono">{m.id}</span>
									<span>·</span>
									<span>{formatSize(m.size_mb)}</span>
									<span>·</span>
									<span>≥ {m.min_ram_gb} GB RAM</span>
									{#if !m.sha256}
										<span>·</span>
										<span class="text-rose-400">unverified — refused at download</span>
									{/if}
								</div>
							</div>
							<div class="flex shrink-0 items-center gap-2">
								{#if status.state === 'downloading'}
									<span class="font-mono text-xs text-ocm-accent">downloading…</span>
								{:else if status.state === 'done'}
									<span class="font-mono text-xs text-emerald-400">downloaded</span>
								{:else if status.state === 'error'}
									<button
										class="rounded border border-rose-700 px-3 py-1 text-xs text-rose-200 hover:bg-rose-950"
										onclick={() => startDownload(m)}
										disabled={!inTauri}
									>
										retry
									</button>
								{:else}
									<button
										class="rounded border border-ocm-accent-dim px-3 py-1 text-xs text-ocm-accent disabled:opacity-30"
										onclick={() => startDownload(m)}
										disabled={!inTauri || !m.sha256}
										title={!inTauri
											? 'Requires the Tauri build'
											: !m.sha256
												? 'Unverified — refused'
												: 'Download to ~/.ocm/data/models'}
									>
										download
									</button>
								{/if}
							</div>
						</div>
						{#if status.state === 'error'}
							<div class="mt-2 font-mono text-[10px] text-rose-300">{status.message}</div>
						{:else if status.state === 'done'}
							<div class="mt-2 font-mono text-[10px] text-ocm-muted">{status.message}</div>
						{/if}
					</div>
				{/each}
			</div>
		{/if}
	</div>
</div>
