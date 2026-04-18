<script lang="ts">
	import { visibleLeaveRequests } from '$lib/hrm/mock-data';
</script>

<section class="header">
	<div>
		<p class="eyebrow">Leave requests</p>
		<h2>Review leave activity</h2>
		<p>Admin sees all requests. Employee mode would only show personal requests through RLS.</p>
	</div>
	<a href="/login">Create request</a>
</section>

<section class="list">
	{#each visibleLeaveRequests as request}
		<article class="card">
			<div class="top">
				<div>
					<h3>{request.employeeName}</h3>
					<p>{request.startDate} to {request.endDate} · {request.totalDays} day(s)</p>
				</div>
				<span class:pending={request.status === 'pending'} class:approved={request.status === 'approved'}>
					{request.status}
				</span>
			</div>
			<p class="reason">{request.reason}</p>
		</article>
	{/each}
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
	h3,
	p {
		margin: 0;
	}

	.header p:last-child {
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

	.list {
		display: grid;
		gap: 14px;
	}

	.card {
		padding: 18px;
		border-radius: 20px;
		background: white;
		border: 1px solid #dbe4f0;
	}

	.top {
		display: flex;
		justify-content: space-between;
		gap: 16px;
		margin-bottom: 10px;
	}

	.top p,
	.reason {
		color: #42536c;
	}

	span {
		display: inline-flex;
		align-self: start;
		padding: 6px 10px;
		border-radius: 999px;
		background: #f4f4f5;
		text-transform: capitalize;
		font-size: 0.88rem;
	}

	.pending {
		background: #fff7df;
		color: #9a6a00;
	}

	.approved {
		background: #e6f8ec;
		color: #1f7a3e;
	}

	@media (max-width: 720px) {
		.header,
		.top {
			flex-direction: column;
			align-items: flex-start;
		}
	}
</style>
