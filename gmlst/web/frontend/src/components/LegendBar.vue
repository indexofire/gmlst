<script>
import { legendItemStyle } from "../visualLayout.js";

export default {
  name: "LegendBar",
  props: {
    items: { type: Array, default: () => [] },
    colorBy: { type: String, default: "" },
    hiddenValues: { type: Object, default: () => ({}) },
    hoveredValue: { type: String, default: null },
  },
  emits: ["toggle", "show-all", "select-by-value", "update:hoveredValue"],
  methods: {
    itemStyle(item) {
      return legendItemStyle(item, this.hiddenValues);
    },
  },
};
</script>
<template>
  <div class="legend">
    <div v-if="items.length === 0" class="legend-title">Legend: fixed node color</div>
    <template v-else>
      <div class="legend-header">
        <span class="legend-title">Legend · {{ colorBy }}</span>
        <button
          v-if="Object.keys(hiddenValues).length > 0"
          class="legend-reset"
          @click="$emit('show-all')"
        >Show all</button>
      </div>
      <span
        v-for="item in items"
        :key="item.value"
        class="legend-item"
        :class="{ 'legend-hidden': hiddenValues[item.value], 'legend-hovered': hoveredValue === item.value }"
        :style="itemStyle(item)"
        tabindex="0"
        role="button"
        :aria-pressed="String(!!hiddenValues[item.value])"
        :aria-label="item.value"
        @click="$emit('toggle', item.value)"
        @keydown.enter="$emit('toggle', item.value)"
        @keydown.space.prevent="$emit('toggle', item.value)"
        @contextmenu.prevent="$emit('select-by-value', item.value)"
        @mouseenter="$emit('update:hoveredValue', item.value)"
        @mouseleave="$emit('update:hoveredValue', null)"
      >
        <span class="dot" :style="{ background: hiddenValues[item.value] ? '#94a3b8' : item.color }"></span>
        {{ item.value }}
        <span class="legend-count">{{ item.count }}</span>
      </span>
    </template>
  </div>
</template>
