<script>
export default {
  name: "EmptyState",
  props: {
    hasProfileInput: { type: Boolean, default: false },
  },
  emits: ["build-mst", "build-distance-matrix", "build-allele-heatmap", "compare-results"],
};
</script>
<template>
  <div class="empty-state">
    <div class="empty-state-intro">
      <div class="empty-state-badge">Start analysis</div>
      <h2>Build a view from your profile table</h2>
      <p>
        Your analysis surface appears here once you build a result. Load a profile TSV in
        the controls, then generate an MST for the clearest first-pass overview.
      </p>
    </div>
    <div class="empty-state-workflow">
      <p class="section-title">Workflow</p>
      <div class="workflow-steps workflow-steps-analysis">
        <div class="workflow-step is-active">1. Load profile TSV</div>
        <div class="workflow-step">2. Build MST or another view</div>
        <div class="workflow-step is-muted">3. Inspect, filter, and compare samples</div>
      </div>
    </div>
    <div class="empty-state-entry-grid">
      <button
        class="empty-state-entry empty-state-entry-primary"
        :disabled="!hasProfileInput"
        @click="$emit('build-mst')"
      >
        <span class="empty-state-entry-label">Recommended first view</span>
        <strong>Build MST</strong>
        <span>
          Best default when you want to understand overall sample relationships quickly.
        </span>
      </button>
      <button
        class="empty-state-entry"
        :disabled="!hasProfileInput"
        @click="$emit('build-distance-matrix')"
      >
        <span class="empty-state-entry-label">Dense comparison</span>
        <strong>Distance matrix</strong>
        <span>Use when you want exact pairwise distances between samples.</span>
      </button>
      <button
        class="empty-state-entry"
        :disabled="!hasProfileInput"
        @click="$emit('build-allele-heatmap')"
      >
        <span class="empty-state-entry-label">Locus-level scan</span>
        <strong>Allele heatmap</strong>
        <span>Use when you want to inspect allele patterns across many loci.</span>
      </button>
      <button class="empty-state-entry" @click="$emit('compare-results')">
        <span class="empty-state-entry-label">Result sets</span>
        <strong>Compare two runs</strong>
        <span>Diff two typing result TSVs from separate runs or pipelines.</span>
      </button>
    </div>
    <div class="empty-state-help-grid">
      <div class="empty-state-help-card">
        <strong>Recommended first pass</strong>
        <ul class="empty-state-list">
          <li>Upload or paste a profile TSV</li>
          <li>Add metadata only if you need coloring or filtering</li>
          <li>Build MST for the clearest first-pass result</li>
        </ul>
      </div>
      <div class="empty-state-help-card">
        <strong>Before you build</strong>
        <ul class="empty-state-list">
          <li v-if="hasProfileInput">Your profile TSV is loaded and ready for analysis</li>
          <li v-else>Load or paste a profile TSV to enable the analysis entry points above</li>
          <li>The table needs a header row and one row per sample</li>
          <li>Use result comparison for comparing two separate TSV outputs</li>
        </ul>
      </div>
    </div>
  </div>
</template>
