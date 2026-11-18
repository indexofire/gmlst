<script>
import { formatNumber } from "../format.js";

export default {
  name: "SummaryView",
  props: {
    summary: { type: Object, default: null },
  },
  methods: { formatNumber },
};
</script>
<template>
  <div class="stats-view">
    <div v-if="!summary" class="stats-empty">
      <p>Build a graph first to see the analysis summary.</p>
    </div>
    <div v-else class="summary-container">
      <div class="summary-hero">
        <div class="summary-hero-metric">
          <strong>{{ formatNumber(summary.sample_count) }}</strong>
          <span>samples</span>
        </div>
        <div class="summary-hero-metric">
          <strong>{{ formatNumber(summary.mst_summary.edges) }}</strong>
          <span>edges</span>
        </div>
        <div class="summary-hero-metric">
          <strong>{{ formatNumber(summary.mst_summary.weight_median) }}</strong>
          <span>median weight</span>
        </div>
        <div class="summary-hero-metric">
          <strong>{{ formatNumber(summary.cluster_count) }}</strong>
          <span>clusters</span>
        </div>
      </div>
      <div v-if="summary.outliers.length" class="summary-section summary-section-warn">
        <h3>⚠ Outliers</h3>
        <div v-for="o in summary.outliers" :key="o.source" class="summary-outlier-row">
          <strong>{{ o.source }} ↔ {{ o.target }}</strong>
          <span class="summary-outlier-w">weight = {{ o.weight }}</span>
        </div>
      </div>
      <div class="summary-section">
        <h3>Hub Nodes (top degree)</h3>
        <div class="summary-hubs">
          <div v-for="nd in summary.top_variable_nodes" :key="nd.label" class="summary-hub">
            <span>{{ nd.label }}</span>
            <strong>{{ nd.degree }}</strong>
          </div>
        </div>
      </div>
      <div class="summary-section">
        <h3>Suggested Analysis</h3>
        <ul class="summary-suggestions">
          <li v-for="(s, i) in summary.suggested_analysis" :key="i">{{ s }}</li>
        </ul>
      </div>
    </div>
  </div>
</template>
