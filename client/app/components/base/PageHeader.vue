<template>
  <div class="flex items-start justify-between gap-4">
    <div>
      <div class="flex items-center gap-2">
        <h1 class="text-xl font-semibold text-highlighted" :class="{ 'font-mono': mono }">{{ title }}</h1>
        <slot name="badge" />
      </div>
      <p v-if="description" class="text-sm text-muted">{{ description }}</p>
    </div>
    <div v-if="$slots.actions" class="flex items-center gap-2 shrink-0">
      <slot name="actions" />
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{ title: string; description?: string; mono?: boolean }>()
</script>
