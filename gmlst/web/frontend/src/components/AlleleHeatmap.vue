<script>
import { heatmapCellClass } from "../visualSelection.js";

export default {
  name: "AlleleHeatmap",
  props: {
    locusQuery: { type: String, default: "" },
    loci: { type: Array, default: () => [] },
    cells: { type: Array, default: () => [] },
    labels: { type: Array, default: () => [] },
    annotationRows: { type: Array, default: () => [] },
    colorBy: { type: String, default: "" },
    truncated: { type: Boolean, default: false },
    renderLimit: { type: Number, default: 0 },
    truncatedCount: { type: Number, default: 0 },
    lociTruncated: { type: Boolean, default: false },
    lociRenderLimit: { type: Number, default: 0 },
    lociTruncatedCount: { type: Number, default: 0 },
  },
  emits: [
    "update:locusQuery",
    "export-tsv",
    "export-json",
    "fill-compare",
    "trigger-compare",
  ],
  methods: {
    cellClass(state) {
      return heatmapCellClass(state);
    },
  },
};
</script>
<template>
  <div class="matrix-panel">
    <div class="table-toolbar">
      <input
        :value="locusQuery"
        @input="$emit('update:locusQuery', $event.target.value)"
        class="table-search"
        type="text"
        placeholder="Filter loci"
      />
      <button class="btn btn-secondary btn-chip" @click="$emit('export-tsv')">
        Export heatmap TSV
      </button>
      <button class="btn btn-secondary btn-chip" @click="$emit('export-json')">
        Export heatmap JSON
      </button>
    </div>
    <div v-if="truncated" class="status-message warn">
      Showing first {{ renderLimit }} of {{ truncatedCount }} rows. Export JSON for full data.
    </div>
    <div v-if="lociTruncated" class="status-message warn">
      Showing first {{ lociRenderLimit }} of {{ lociTruncatedCount }} loci. Use locus filter to narrow.
    </div>
    <table class="matrix-table">
      <thead>
        <tr>
          <th></th>
          <th v-if="colorBy">{{ colorBy }}</th>
          <th v-for="locus in loci" :key="locus">{{ locus }}</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="(row, rowIndex) in cells"
          :key="labels[rowIndex] || rowIndex"
        >
          <th
            @click="$emit('fill-compare', labels[rowIndex])"
            @dblclick="$emit('trigger-compare', labels[rowIndex])"
          >
            {{ labels[rowIndex] || rowIndex }}
          </th>
          <td v-if="colorBy">
            <div
              class="matrix-cell annotation-cell"
              :style="{ background: annotationRows[rowIndex]?.color || '#e5e7eb' }"
              :title="`${labels[rowIndex]} · ${colorBy}: ${annotationRows[rowIndex]?.value || '-'}`"
            >
              {{ annotationRows[rowIndex]?.value || '-' }}
            </div>
          </td>
          <td v-for="(cell, cellIndex) in row" :key="`${rowIndex}-${cellIndex}`">
            <div
              class="matrix-cell"
              :class="cellClass(cell.state)"
              :title="`${labels[rowIndex]} · ${loci[cellIndex]}: ${cell.value} (${cell.state})`"
            >
              {{ cell.value }}
            </div>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
