<section class="login-grid">
	<div class="panel">
		<p class="label">Auth screen</p>
		<h2>Sign in to HRM Mini</h2>
		<p>
			This UI is ready for Supabase Auth. In demo mode, use it as a reference screen and continue
			to the dashboard.
		</p>

		<form class="form">
			<label>
				<span>Email</span>
				<input type="email" placeholder="alex@bardo-hrm.demo" />
			</label>
			<label>
				<span>Password</span>
				<input type="password" placeholder="••••••••" />
			</label>
			<div class="row">
				<button type="button">Sign in with Supabase</button>
				<a href="/dashboard">Continue to demo</a>
			</div>
		</form>
	</div>

	<div class="panel soft">
		<h3>Suggested Auth flow</h3>
		<ul>
			<li>Supabase email/password or magic link.</li>
			<li>Admin lands on dashboard, employee lands on personal view.</li>
			<li>JWT claims and membership role feed RLS decisions.</li>
		</ul>
	</div>
</section>

<style>
	.login-grid {
		display: grid;
		grid-template-columns: 1.4fr 1fr;
		gap: 20px;
	}

	.panel {
		padding: 24px;
		border-radius: 22px;
		background: white;
		border: 1px solid #dbe4f0;
	}

	.soft {
		background: linear-gradient(180deg, #eef4ff 0%, #f8fbff 100%);
	}

	.label {
		margin: 0 0 8px;
		font-size: 0.88rem;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: #5a6f8d;
	}

	h2,
	h3 {
		margin-top: 0;
	}

	p,
	li {
		color: #42536c;
	}

	.form {
		display: grid;
		gap: 14px;
		margin-top: 18px;
	}

	label {
		display: grid;
		gap: 6px;
	}

	span {
		font-size: 0.92rem;
		font-weight: 600;
	}

	input {
		padding: 12px 14px;
		border-radius: 12px;
		border: 1px solid #cfd8e3;
		font: inherit;
	}

	.row {
		display: flex;
		gap: 12px;
		align-items: center;
	}

	button,
	a {
		padding: 12px 16px;
		border-radius: 12px;
		font-weight: 600;
	}

	button {
		border: none;
		background: #1e66f5;
		color: white;
		cursor: pointer;
	}

	a {
		background: #eef4ff;
		color: #1d4ed8;
	}

	@media (max-width: 720px) {
		.login-grid {
			grid-template-columns: 1fr;
		}
	}
</style>
