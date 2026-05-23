<script setup lang="ts">
import type { Assessment } from "../api/client";

defineProps<{
  items: Assessment[];
  loading: boolean;
}>();

const emit = defineEmits<{ remove: [id: number] }>();
</script>

<template>
  <div v-if="loading" class="empty">Loading assessments...</div>
  <p v-else-if="items.length === 0" class="empty">No assessments yet. Create the first one.</p>
  <table v-else>
    <thead>
      <tr>
        <th>Title</th>
        <th>Subject</th>
        <th>Score</th>
        <th>Status</th>
        <th></th>
      </tr>
    </thead>
    <tbody>
      <tr v-for="item in items" :key="item.id">
        <td>{{ item.title }}</td>
        <td>{{ item.subject_name }}</td>
        <td>{{ item.score.toFixed(1) }}</td>
        <td><span class="status-pill" :class="item.status">{{ item.status }}</span></td>
        <td><button class="danger" type="button" @click="emit('remove', item.id)">Delete</button></td>
      </tr>
    </tbody>
  </table>
</template>
