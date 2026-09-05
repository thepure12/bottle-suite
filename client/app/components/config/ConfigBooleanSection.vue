<template>
  <div class="flex items-center justify-between py-3">
    <div class="flex items-center gap-3">
      <UIcon v-if="icon" :name="icon" class="size-5 text-muted shrink-0" />
      <div>
        <p class="font-medium">{{ label }}</p>
        <p v-if="description" class="text-sm text-muted">{{ description }}</p>
      </div>
    </div>
    <div class="flex items-center gap-3">
      <UBadge :color="enabled ? 'success' : 'neutral'" variant="subtle" size="sm">
        {{ enabled ? 'Enabled' : 'Disabled' }}
      </UBadge>
      <USwitch v-model="enabled" />
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{ label: string; description?: string; icon?: string }>()
const enabled = defineModel<boolean>({ required: true })
</script>
