<script lang="ts">
	import { onMount } from 'svelte';
	import { chatStream, listModels } from '$lib/api';
	import type { ChatMessage } from '$lib/types';

	let models = $state<string[]>([]);
	let selectedModel = $state<string>('ocm-default');
	let modelsError = $state<string | null>(null);

	let input = $state('');
	let messages = $state<ChatMessage[]>([]);
	let busy = $state(false);
	let chatError = $state<string | null>(null);
	let streamingResponse = $state('');

	let abortController: AbortController | null = null;

	onMount(async () => {
		try {
			const ids = await listModels();
			models = ids;
			if (ids.length > 0 && !ids.includes(selectedModel)) {
				selectedModel = ids[0];
			}
		} catch (e) {
			modelsError = e instanceof Error ? e.message : String(e);
		}
	});

	async function send() {
		const trimmed = input.trim();
		if (!trimmed || busy) return;

		const userMsg: ChatMessage = { role: 'user', content: trimmed };
		messages = [...messages, userMsg];
		input = '';
		busy = true;
		chatError = null;
		streamingResponse = '';
		abortController = new AbortController();

		try {
			await chatStream(
				selectedModel,
				messages,
				(token) => {
					streamingResponse += token;
				},
				abortController.signal
			);
			messages = [...messages, { role: 'assistant', content: streamingResponse }];
			streamingResponse = '';
		} catch (e) {
			if ((e as Error).name === 'AbortError') {
				// User stopped; preserve whatever streamed in
				if (streamingResponse) {
					messages = [...messages, { role: 'assistant', content: streamingResponse }];
					streamingResponse = '';
				}
			} else {
				chatError = e instanceof Error ? e.message : String(e);
			}
		} finally {
			busy = false;
			abortController = null;
		}
	}

	function stop() {
		abortController?.abort();
	}

	function reset() {
		messages = [];
		streamingResponse = '';
		chatError = null;
	}

	function onKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter' && !e.shiftKey) {
			e.preventDefault();
			send();
		}
	}
</script>

<div class="flex h-full flex-col">
	<!-- Model picker -->
	<div class="flex items-center gap-3 border-b border-ocm-border bg-ocm-surface px-4 py-2">
		<label for="model" class="text-xs text-ocm-muted">model</label>
		{#if modelsError}
			<span class="font-mono text-xs text-rose-400">daemon unreachable: {modelsError}</span>
		{:else if models.length === 0}
			<span class="font-mono text-xs text-ocm-muted">loading…</span>
		{:else}
			<select
				id="model"
				bind:value={selectedModel}
				class="rounded border border-ocm-border bg-ocm-bg px-2 py-1 font-mono text-xs"
			>
				{#each models as m (m)}
					<option value={m}>{m}</option>
				{/each}
			</select>
		{/if}
		<div class="flex-1"></div>
		<button
			class="rounded border border-ocm-border px-2 py-1 text-xs text-ocm-muted hover:text-slate-100 disabled:opacity-30"
			disabled={messages.length === 0 || busy}
			onclick={reset}
		>
			clear
		</button>
	</div>

	<!-- Transcript -->
	<div class="flex-1 space-y-3 overflow-y-auto px-4 py-4">
		{#each messages as m (m)}
			<div class="flex gap-3">
				<span
					class="shrink-0 font-mono text-xs uppercase {m.role === 'user'
						? 'text-ocm-accent'
						: 'text-ocm-accent-dim'}"
				>
					{m.role}
				</span>
				<div class="flex-1 whitespace-pre-wrap">{m.content}</div>
			</div>
		{/each}
		{#if streamingResponse}
			<div class="flex gap-3">
				<span class="shrink-0 font-mono text-xs uppercase text-ocm-accent-dim">assistant</span>
				<div class="flex-1 whitespace-pre-wrap">{streamingResponse}<span class="opacity-50">▋</span></div>
			</div>
		{/if}
		{#if chatError}
			<div class="rounded border border-rose-700 bg-rose-950 px-3 py-2 font-mono text-xs text-rose-200">
				{chatError}
			</div>
		{/if}
		{#if messages.length === 0 && !streamingResponse}
			<div class="text-sm text-ocm-muted">
				Type a message below. The daemon will retrieve relevant memories from Mem0
				before generating a response.
			</div>
		{/if}
	</div>

	<!-- Composer -->
	<div class="border-t border-ocm-border bg-ocm-surface p-3">
		<div class="flex gap-2">
			<textarea
				class="min-h-12 flex-1 resize-none rounded border border-ocm-border bg-ocm-bg px-3 py-2 font-mono text-sm focus:border-ocm-accent-dim focus:outline-none"
				placeholder="Ask anything…"
				bind:value={input}
				onkeydown={onKeydown}
				disabled={busy}
				rows="2"
			></textarea>
			{#if busy}
				<button
					class="rounded border border-rose-700 bg-rose-900 px-3 py-2 text-sm text-rose-100"
					onclick={stop}
				>
					stop
				</button>
			{:else}
				<button
					class="rounded border border-ocm-accent-dim bg-ocm-accent-dim px-3 py-2 text-sm text-ocm-bg disabled:opacity-30"
					disabled={!input.trim()}
					onclick={send}
				>
					send
				</button>
			{/if}
		</div>
		<div class="mt-1 text-[10px] text-ocm-muted">enter sends · shift+enter newline</div>
	</div>
</div>
