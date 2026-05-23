<script setup lang="ts">
import { onMounted, ref } from "vue";
import { api, type Assessment, type BillingStatus } from "./api/client";
import AssessmentForm from "./components/AssessmentForm.vue";
import AssessmentList from "./components/AssessmentList.vue";
import BillingPanel from "./components/BillingPanel.vue";

const assessments = ref<Assessment[]>([]);
const billing = ref<BillingStatus | null>(null);
const loadingAssessments = ref(false);
const loadingBilling = ref(false);
const error = ref("");

async function refreshAll() {
  loadingAssessments.value = true;
  loadingBilling.value = true;
  error.value = "";
  try {
    const [assessmentData, billingData] = await Promise.all([
      api.listAssessments(),
      api.getBillingStatus(),
    ]);
    assessments.value = assessmentData;
    billing.value = billingData;
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Failed to load data";
  } finally {
    loadingAssessments.value = false;
    loadingBilling.value = false;
  }
}

async function removeAssessment(id: number) {
  try {
    await api.deleteAssessment(id);
    await refreshAll();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Failed to delete assessment";
  }
}

onMounted(refreshAll);
</script>

<template>
  <header>
    <h1>Assessment Billing Demo</h1>
    <p>FastAPI + Vue.js + TypeScript portfolio app for user assessments and billing usage.</p>
  </header>

  <p v-if="error" class="error">{{ error }}</p>

  <div class="layout">
    <section class="card">
      <h2>Create assessment</h2>
      <AssessmentForm @created="refreshAll" />
    </section>

    <aside class="card">
      <h2>Billing status</h2>
      <BillingPanel :billing="billing" :loading="loadingBilling" />
    </aside>
  </div>

  <section class="card" style="margin-top: 20px">
    <div style="display: flex; justify-content: space-between; align-items: center; gap: 12px">
      <h2>Assessments</h2>
      <button class="secondary" type="button" @click="refreshAll">Refresh</button>
    </div>
    <AssessmentList
      :items="assessments"
      :loading="loadingAssessments"
      @remove="removeAssessment"
    />
  </section>
</template>
