<template>
  <div class="flex flex-col items-center gap-3 py-10 text-center">
    <UIcon :name="icon" class="size-8 text-dimmed" />
    <p class="text-sm text-muted max-w-xs">{{ message }}</p>
    <slot name="action" />
  </div>
</template>

<script setup lang="ts">
defineProps<{ icon: string; message: string }>()
</script>
