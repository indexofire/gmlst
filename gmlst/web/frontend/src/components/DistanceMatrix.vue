<script>
import { matrixCellTitle } from "../visualSelection.js";

export default {
  name: "DistanceMatrix",
  props: {
    labels: { type: Array, default: () => [] },
    matrix: { type: Array, default: () => [] },
    maxValue: { type: Number, default: 0 },
    truncated: { type: Boolean, default: false },
    renderLimit: { type: Number, default: 0 },
    truncatedCount: { type: Number, default: 0 },
  },
  emits: ["compare-pair"],
  methods: {
    cellTitle(rowLabel, colLabel, value) {
      return matrixCellTitle(rowLabel, colLabel, value);
    },
    cellStyle(value) {
      const ratio = (Number(value) || 0) / this.maxValue;
      return {
        backgroundColor: `rgba(30, 93, 168, ${Number(value) === 0 ? 0.06 : Math.max(0.1, ratio * 0.62)})`,
        color: ratio > 0.62 ? "#f8fafc" : "#1e293b",
      };
    },
  },
};
</script>
<template>
  <div class="matrix-panel">
    <div v-if="truncated" class="status-message warn">
      Showing first {{ renderLimit }} of {{ truncatedCount }} rows. Export JSON for full data.
    </div>
    <table class="matrix-table">
      <thead>
        <tr>
          <th></th>
          <th v-for="label in labels" :key="label">{{ label }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(row, rowIndex) in matrix" :key="labels[rowIndex] || rowIndex">
          <th>{{ labels[rowIndex] || rowIndex }}</th>
          <td v-for="(value, colIndex) in row" :key="`${rowIndex}-${colIndex}`">
            <div
              class="matrix-cell"
              :style="cellStyle(value)"
              :title="cellTitle(labels[rowIndex], labels[colIndex], value)"
              @click="$emit('compare-pair', labels[rowIndex], labels[colIndex])"
            >
              {{ value }}
            </div>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
