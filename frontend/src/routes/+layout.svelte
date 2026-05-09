<script lang="ts">
	import '../app.css';

	let { children } = $props();
</script>

<main class="flex h-screen flex-col bg-ocm-bg text-slate-100">
	<header
		class="flex items-center justify-between border-b border-ocm-border bg-ocm-surface px-4 py-2"
	>
		<div class="flex items-center gap-2">
			<span class="h-2 w-2 rounded-full bg-ocm-accent"></span>
			<span class="font-mono text-sm tracking-wide">OpenCircuitModel</span>
		</div>
		<span class="text-xs text-ocm-muted">v0.1.0 · local daemon</span>
	</header>
	<div class="flex-1 overflow-hidden">
		{@render children()}
	</div>
</main>
