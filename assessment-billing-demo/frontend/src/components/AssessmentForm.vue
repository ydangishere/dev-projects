<script setup lang="ts">
import { reactive, ref } from "vue";
import { api, type AssessmentCreate } from "../api/client";

const emit = defineEmits<{ created: [] }>();

const form = reactive<AssessmentCreate>({
  title: "",
  subject_name: "",
  score: 80,
  status: "draft",
  notes: "",
});

const loading = ref(false);
const error = ref("");

async function submit() {
  loading.value = true;
  error.value = "";
  try {
    await api.createAssessment({
      ...form,
      notes: form.notes?.trim() ? form.notes : undefined,
    });
    form.title = "";
    form.subject_name = "";
    form.score = 80;
    form.status = "draft";
    form.notes = "";
    emit("created");
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Failed to create assessment";
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <form @submit.prevent="submit">
    <label>
      Title
      <input v-model="form.title" required placeholder="Quarterly device audit" />
    </label>
    <label>
      Subject
      <input v-model="form.subject_name" required placeholder="Clinic / manufacturer name" />
    </label>
    <label>
      Score
      <input v-model.number="form.score" type="number" min="0" max="100" step="0.1" required />
    </label>
    <label>
      Status
      <select v-model="form.status">
        <option value="draft">Draft</option>
        <option value="submitted">Submitted</option>
        <option value="reviewed">Reviewed</option>
      </select>
    </label>
    <label>
      Notes
      <textarea v-model="form.notes" rows="3" placeholder="Optional assessment notes" />
    </label>
    <button type="submit" :disabled="loading">{{ loading ? "Saving..." : "Create assessment" }}</button>
    <p v-if="error" class="error">{{ error }}</p>
  </form>
</template>
