<template>
  <UCard>
    <div class="flex items-center gap-3">
      <UIcon :name="icon" class="size-6 text-primary shrink-0" />
      <div>
        <p class="text-2xl font-semibold font-mono">{{ value }}</p>
        <p class="text-sm text-muted">{{ label }}</p>
      </div>
    </div>
  </UCard>
</template>

<script setup lang="ts">
defineProps<{ icon: string; value: string | number; label: string }>()
</script>
