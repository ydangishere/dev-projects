<section class="hero">
	<div class="copy">
		<p class="kicker">Mini product demo for portfolio</p>
		<h2>Web-based HRM demo built to showcase SvelteKit + Supabase structure</h2>
		<p>
			This mini app focuses on four screens: login, dashboard, employees, and leave requests. It
			is small enough to ship fast, but still shows auth, roles, schema thinking, and RLS-friendly
			data boundaries.
		</p>
		<div class="actions">
			<a class="primary" href="/dashboard">Open dashboard</a>
			<a class="secondary" href="/login">View login flow</a>
		</div>
	</div>

	<div class="card">
		<h3>What this repo proves</h3>
		<ul>
			<li>SvelteKit routes and page composition for a product-like web app.</li>
			<li>Supabase-ready setup: Auth, Postgres, Row Level Security, and Storage scope.</li>
			<li>Role-aware HRM structure with admin and employee views.</li>
		</ul>
	</div>
</section>

<style>
	.hero {
		display: grid;
		grid-template-columns: 1.6fr 1fr;
		gap: 20px;
	}

	.copy,
	.card {
		padding: 24px;
		border-radius: 22px;
		background: white;
		border: 1px solid #dbe4f0;
	}

	.kicker {
		margin: 0 0 8px;
		color: #5a6f8d;
		font-size: 0.9rem;
		text-transform: uppercase;
		letter-spacing: 0.06em;
	}

	h2 {
		margin: 0 0 12px;
		font-size: 2rem;
		line-height: 1.15;
	}

	p {
		margin: 0 0 16px;
		color: #42536c;
	}

	.actions {
		display: flex;
		gap: 12px;
	}

	.primary,
	.secondary {
		padding: 12px 16px;
		border-radius: 12px;
		font-weight: 600;
	}

	.primary {
		background: #1e66f5;
		color: white;
	}

	.secondary {
		background: #eef4ff;
		color: #1d4ed8;
	}

	h3 {
		margin-top: 0;
	}

	ul {
		margin: 0;
		padding-left: 18px;
		color: #42536c;
	}

	li + li {
		margin-top: 10px;
	}

	@media (max-width: 720px) {
		.hero {
			grid-template-columns: 1fr;
		}
	}
</style>
