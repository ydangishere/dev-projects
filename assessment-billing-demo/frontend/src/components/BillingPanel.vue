<script setup lang="ts">
import type { BillingStatus } from "../api/client";

defineProps<{
  billing: BillingStatus | null;
  loading: boolean;
}>();
</script>

<template>
  <div v-if="loading" class="empty">Loading billing...</div>
  <div v-else-if="billing" class="billing-grid">
    <div class="metric"><span>Plan</span><strong>{{ billing.plan }}</strong></div>
    <div class="metric"><span>Status</span><strong>{{ billing.status }}</strong></div>
    <div class="metric"><span>Used</span><strong>{{ billing.assessments_used }}</strong></div>
    <div class="metric"><span>Limit</span><strong>{{ billing.assessments_limit }}</strong></div>
    <div class="metric"><span>Remaining</span><strong>{{ billing.remaining }}</strong></div>
  </div>
</template>
