<script lang="ts">
	import favicon from '$lib/assets/favicon.svg';

	let { children } = $props();

	const navItems = [
		{ href: '/', label: 'Overview' },
		{ href: '/login', label: 'Login' },
		{ href: '/dashboard', label: 'Dashboard' },
		{ href: '/employees', label: 'Employees' },
		{ href: '/leave-requests', label: 'Leave Requests' }
	];
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
	<title>HRM Mini - SvelteKit + Supabase</title>
</svelte:head>

<div class="app-shell">
	<header class="topbar">
		<div>
			<p class="eyebrow">SvelteKit + Supabase demo</p>
			<h1>HRM Mini</h1>
		</div>
		<nav>
			{#each navItems as item}
				<a href={item.href}>{item.label}</a>
			{/each}
		</nav>
	</header>

	<div class="notice">
		Demo mode uses local mock data for quick preview. The repo also includes Supabase-ready auth,
		schema, and RLS files for wiring a real project.
	</div>

	<main>
		{@render children()}
	</main>
</div>

<style>
	:global(body) {
		margin: 0;
		font-family:
			Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
		background: #f4f7fb;
		color: #122033;
	}

	:global(a) {
		color: inherit;
		text-decoration: none;
	}

	.app-shell {
		max-width: 1120px;
		margin: 0 auto;
		padding: 24px;
	}

	.topbar {
		display: flex;
		justify-content: space-between;
		align-items: flex-end;
		gap: 16px;
		margin-bottom: 16px;
	}

	.eyebrow {
		margin: 0 0 4px;
		font-size: 0.85rem;
		color: #52627a;
		text-transform: uppercase;
		letter-spacing: 0.08em;
	}

	h1 {
		margin: 0;
		font-size: 2rem;
	}

	nav {
		display: flex;
		flex-wrap: wrap;
		gap: 10px;
	}

	nav a {
		padding: 10px 14px;
		border-radius: 999px;
		background: white;
		border: 1px solid #d8e2f0;
		font-size: 0.95rem;
	}

	.notice {
		margin-bottom: 20px;
		padding: 12px 14px;
		border-radius: 14px;
		background: #e9f4ff;
		border: 1px solid #c8e0ff;
		color: #26456f;
		font-size: 0.95rem;
	}

	main {
		display: block;
	}

	@media (max-width: 720px) {
		.topbar {
			flex-direction: column;
			align-items: flex-start;
		}
	}
</style>
