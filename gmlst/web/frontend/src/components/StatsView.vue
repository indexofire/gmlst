<script>
import { formatNumber } from "../format.js";

export default {
  name: "StatsView",
  props: {
    stats: { type: Object, default: null },
  },
  methods: { formatNumber },
};
</script>
<template>
  <div class="stats-view">
    <div v-if="!stats" class="stats-empty">
      <p>Build a graph first to see statistics.</p>
    </div>
    <div v-else class="stats-grid">
    <div class="stats-card">
      <h3>Overview</h3>
      <div class="stats-metrics">
        <div class="stats-metric"><span>Samples</span><strong>{{ formatNumber(stats.nodeCount) }}</strong></div>
        <div class="stats-metric"><span>Edges</span><strong>{{ formatNumber(stats.edgeCount) }}</strong></div>
        <div class="stats-metric"><span>Clusters</span><strong>{{ formatNumber(stats.clusterCount) }}</strong></div>
        <div class="stats-metric"><span>Zero-weight pairs</span><strong>{{ formatNumber(stats.zeroWeightCount) }}</strong></div>
      </div>
    </div>
    <div class="stats-card">
      <h3>Edge Weight Distribution</h3>
      <div class="stats-quartiles">
        <span>min: {{ stats.weightMin }}</span>
        <span>Q25: {{ stats.weightQ25 }}</span>
        <span>median: {{ stats.weightMedian }}</span>
        <span>Q75: {{ stats.weightQ75 }}</span>
        <span>max: {{ stats.weightMax }}</span>
      </div>
      <div class="stats-histogram">
        <div
          v-for="bin in stats.histogram"
          :key="bin.label"
          class="stats-hist-bar"
          :style="{ height: Math.max(4, bin.pct * 1.8) + 'px' }"
          :title="`${bin.label}: ${bin.count} (${bin.pct}%)`"
        />
      </div>
      <div class="stats-hist-labels">
        <span>{{ stats.weightMin }}</span>
        <span>{{ stats.weightMax }}</span>
      </div>
    </div>
    <div class="stats-card">
      <h3>Top Degree Nodes</h3>
      <table class="stats-table">
        <thead>
          <tr><th>Node</th><th>Degree</th></tr>
        </thead>
        <tbody>
          <tr v-for="nd in stats.topDegree" :key="nd.label">
            <td>{{ nd.label }}</td>
            <td class="stats-num">{{ formatNumber(nd.degree) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-if="stats.outliers.length" class="stats-card stats-card-warning">
      <h3>Outlier Alerts</h3>
      <div v-for="o in stats.outliers" :key="o.source + o.target" class="stats-outlier">
        <span class="stats-outlier-pair">{{ o.source }} ↔ {{ o.target }}</span>
        <span class="stats-outlier-w">w={{ o.weight }}</span>
      </div>
    </div>
    </div>
  </div>
</template>
