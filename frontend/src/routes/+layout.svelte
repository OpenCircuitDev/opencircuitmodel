<script lang="ts">
	import { page } from '$app/state';
	import '../app.css';

	let { children } = $props();

	const navLinks = [
		{ href: '/', label: 'chat' },
		{ href: '/models/', label: 'models' },
		{ href: '/settings/', label: 'settings' }
	];
</script>

<main class="flex h-screen flex-col bg-ocm-bg text-slate-100">
	<header
		class="flex items-center justify-between border-b border-ocm-border bg-ocm-surface px-4 py-2"
	>
		<div class="flex items-center gap-3">
			<span class="h-2 w-2 rounded-full bg-ocm-accent"></span>
			<span class="font-mono text-sm tracking-wide">OpenCircuitModel</span>
			<nav class="flex items-center gap-3 pl-3">
				{#each navLinks as link (link.href)}
					{@const active =
						page.url.pathname === link.href ||
						(link.href !== '/' && page.url.pathname.startsWith(link.href))}
					<a
						href={link.href}
						class="font-mono text-xs uppercase tracking-wide transition-colors {active
							? 'text-ocm-accent'
							: 'text-ocm-muted hover:text-slate-100'}"
					>
						{link.label}
					</a>
				{/each}
			</nav>
		</div>
		<span class="text-xs text-ocm-muted">v0.1.0 · local daemon</span>
	</header>
	<div class="flex-1 overflow-hidden">
		{@render children()}
	</div>
</main>
