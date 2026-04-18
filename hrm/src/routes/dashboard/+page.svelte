<script lang="ts">
	import {
		currentViewer,
		dashboardSummary,
		departments,
		visibleLeaveRequests
	} from '$lib/hrm/mock-data';

	const cards = [
		{ label: 'Total employees', value: dashboardSummary.totalEmployees },
		{ label: 'Active employees', value: dashboardSummary.activeEmployees },
		{ label: 'Pending leave requests', value: dashboardSummary.pendingLeaveRequests },
		{ label: 'Approved leave days', value: dashboardSummary.approvedLeaveDays }
	];
</script>

<section class="page-header">
	<div>
		<p class="eyebrow">Dashboard</p>
		<h2>Welcome back, {currentViewer.fullName}</h2>
		<p>Admin view across headcount, departments, and leave activity.</p>
	</div>
	<div class="viewer-badge">{currentViewer.role}</div>
</section>

<section class="cards">
	{#each cards as card}
		<article class="card">
			<p>{card.label}</p>
			<h3>{card.value}</h3>
		</article>
	{/each}
</section>

<section class="grid">
	<article class="panel">
		<h3>Departments</h3>
		<ul>
			{#each departments as department}
				<li>{department}</li>
			{/each}
		</ul>
	</article>

	<article class="panel">
		<h3>Latest leave requests</h3>
		{#each visibleLeaveRequests as request}
			<div class="request">
				<div>
					<strong>{request.employeeName}</strong>
					<p>{request.startDate} to {request.endDate}</p>
				</div>
				<span class:pending={request.status === 'pending'} class:approved={request.status === 'approved'}>
					{request.status}
				</span>
			</div>
		{/each}
	</article>
</section>

<style>
	.page-header,
	.cards,
	.grid {
		display: grid;
		gap: 16px;
	}

	.page-header {
		grid-template-columns: 1fr auto;
		align-items: center;
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
	h3,
	p {
		margin: 0;
	}

	.page-header p:last-child {
		margin-top: 6px;
		color: #42536c;
	}

	.viewer-badge {
		padding: 10px 14px;
		border-radius: 999px;
		background: #e8f3ff;
		color: #1d4ed8;
		font-weight: 700;
		text-transform: capitalize;
	}

	.cards {
		grid-template-columns: repeat(4, minmax(0, 1fr));
		margin-bottom: 16px;
	}

	.card,
	.panel {
		padding: 20px;
		border-radius: 20px;
		background: white;
		border: 1px solid #dbe4f0;
	}

	.card p {
		color: #52627a;
		margin-bottom: 10px;
	}

	.card h3 {
		font-size: 1.8rem;
	}

	.grid {
		grid-template-columns: 0.9fr 1.1fr;
	}

	ul {
		margin: 12px 0 0;
		padding-left: 18px;
		color: #42536c;
	}

	.request {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 14px 0;
		border-bottom: 1px solid #edf1f7;
	}

	.request:last-child {
		border-bottom: none;
		padding-bottom: 0;
	}

	.request p {
		margin-top: 4px;
		color: #61738e;
		font-size: 0.92rem;
	}

	span {
		padding: 6px 10px;
		border-radius: 999px;
		background: #eef4ff;
		text-transform: capitalize;
		font-size: 0.9rem;
	}

	.pending {
		background: #fff7df;
		color: #9a6a00;
	}

	.approved {
		background: #e6f8ec;
		color: #1f7a3e;
	}

	@media (max-width: 900px) {
		.cards,
		.grid {
			grid-template-columns: 1fr 1fr;
		}
	}

	@media (max-width: 720px) {
		.page-header,
		.cards,
		.grid {
			grid-template-columns: 1fr;
		}
	}
</style>
