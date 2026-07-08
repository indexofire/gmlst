<script>
export default {
  name: "CompareTable",
  props: {
    summary: { type: Object, default: null },
    rows: { type: Array, default: () => [] },
    statusOptions: { type: Array, default: () => [] },
    statusFilter: { type: String, default: "" },
  },
  emits: ["update:statusFilter"],
};
</script>
<template>
  <div class="matrix-panel">
    <div v-if="summary" class="compare-summary-grid">
      <div class="metric"><span>Matched</span><strong>{{ summary.matched_samples }}</strong></div>
      <div class="metric"><span>Same ST</span><strong>{{ summary.same_st }}</strong></div>
      <div class="metric"><span>Different ST</span><strong>{{ summary.different_st }}</strong></div>
      <div class="metric"><span>Locus diff</span><strong>{{ summary.samples_with_locus_differences }}</strong></div>
      <div class="metric"><span>Left only</span><strong>{{ summary.left_only }}</strong></div>
      <div class="metric"><span>Right only</span><strong>{{ summary.right_only }}</strong></div>
    </div>
    <div class="table-toolbar">
      <select
        :value="statusFilter"
        @change="$emit('update:statusFilter', $event.target.value)"
      >
        <option value="">All statuses</option>
        <option v-for="option in statusOptions" :key="option.value" :value="option.value">
          {{ option.label }}
        </option>
      </select>
    </div>
    <table class="isolate-table">
      <thead>
        <tr>
          <th>Sample</th>
          <th>Left ST</th>
          <th>Right ST</th>
          <th>Diff loci</th>
          <th>Status</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="row.sample_id">
          <td>{{ row.sample_id }}</td>
          <td>{{ row.left_st || '-' }}</td>
          <td>{{ row.right_st || '-' }}</td>
          <td>{{ row.differing_loci_count }}</td>
          <td>{{ row.status }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
