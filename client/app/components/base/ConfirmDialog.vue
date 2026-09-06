<template>
  <UModal v-model:open="open" :title="title">
    <template #body>
      <p class="text-sm text-muted">{{ message }}</p>
    </template>
    <template #footer>
      <UButton color="neutral" variant="ghost" @click="open = false">Cancel</UButton>
      <UButton color="error" :loading="loading" @click="emit('confirm')">{{ confirmLabel ?? 'Delete' }}</UButton>
    </template>
  </UModal>
</template>

<script setup lang="ts">
const open = defineModel<boolean>('open', { default: false })

defineProps<{
  title: string
  message: string
  confirmLabel?: string
  loading?: boolean
}>()

const emit = defineEmits<{ confirm: [] }>()
</script>
