<script>
export default {
  name: "BuildPrompt",
  props: {
    title: { type: String, required: true },
    description: { type: String, default: "" },
    actionLabel: { type: String, default: "Build view" },
    hasInput: { type: Boolean, default: true },
    inputHint: { type: String, default: "Load your data first." },
  },
  emits: ["action"],
};
</script>
<template>
  <div class="build-prompt">
    <span class="build-prompt-badge">Not built yet</span>
    <h3>{{ title }}</h3>
    <p v-if="description" class="build-prompt-copy">{{ description }}</p>
    <p v-if="!hasInput" class="build-prompt-hint">{{ inputHint }}</p>
    <button
      class="btn btn-primary build-prompt-action"
      type="button"
      :disabled="!hasInput"
      @click="$emit('action')"
    >
      {{ actionLabel }}
    </button>
  </div>
</template>
