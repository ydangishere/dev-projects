<script lang="ts">
	import { canManageEmployees } from '$lib/hrm/hrm';
	import { currentViewer, visibleEmployees } from '$lib/hrm/mock-data';
</script>

<section class="header">
	<div>
		<p class="eyebrow">Employees</p>
		<h2>Employee directory</h2>
		<p>Admin can manage all employees. Employee view would only show the signed-in profile.</p>
	</div>
	{#if canManageEmployees(currentViewer.role)}
		<a href="/login">Invite employee</a>
	{/if}
</section>

<section class="table-shell">
	<table>
		<thead>
			<tr>
				<th>Name</th>
				<th>Department</th>
				<th>Role</th>
				<th>Status</th>
				<th>Email</th>
			</tr>
		</thead>
		<tbody>
			{#each visibleEmployees as employee}
				<tr>
					<td>{employee.fullName}</td>
					<td>{employee.department}</td>
					<td><span class="chip">{employee.role}</span></td>
					<td><span class:active={employee.status === 'active'}>{employee.status}</span></td>
					<td>{employee.email}</td>
				</tr>
			{/each}
		</tbody>
	</table>
</section>

<style>
	.header {
		display: flex;
		justify-content: space-between;
		align-items: end;
		gap: 16px;
		margin-bottom: 16px;
	}

	.eyebrow {
		margin: 0 0 4px;
		font-size: 0.88rem;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: #5a6f8d;
	}

	h2,
	p {
		margin: 0;
	}

	p:last-child {
		margin-top: 6px;
		color: #42536c;
	}

	a {
		padding: 12px 16px;
		border-radius: 12px;
		background: #1e66f5;
		color: white;
		font-weight: 600;
	}

	.table-shell {
		padding: 16px;
		border-radius: 20px;
		background: white;
		border: 1px solid #dbe4f0;
		overflow: auto;
	}

	table {
		width: 100%;
		border-collapse: collapse;
	}

	th,
	td {
		padding: 14px 12px;
		text-align: left;
		border-bottom: 1px solid #edf1f7;
	}

	th {
		color: #52627a;
		font-size: 0.92rem;
	}

	.chip,
	.active,
	span {
		display: inline-flex;
		padding: 6px 10px;
		border-radius: 999px;
		background: #eef4ff;
		text-transform: capitalize;
		font-size: 0.88rem;
	}

	.active {
		background: #e6f8ec;
		color: #1f7a3e;
	}

	@media (max-width: 720px) {
		.header {
			flex-direction: column;
			align-items: flex-start;
		}
	}
</style>
