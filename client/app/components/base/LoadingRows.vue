<template>
  <div v-if="variant === 'stat'" class="grid grid-cols-1 sm:grid-cols-3 gap-4">
    <UCard v-for="i in count" :key="i">
      <div class="flex items-center gap-3">
        <USkeleton class="size-6 rounded-full shrink-0" />
        <div class="space-y-2">
          <USkeleton class="h-6 w-12" />
          <USkeleton class="h-3 w-20" />
        </div>
      </div>
    </UCard>
  </div>

  <div v-else-if="variant === 'card'" class="grid grid-cols-1 sm:grid-cols-2 gap-3">
    <div v-for="i in count" :key="i" class="border border-default rounded-lg p-4 flex items-center gap-3">
      <USkeleton class="size-5 rounded-full shrink-0" />
      <USkeleton class="h-4 flex-1" />
    </div>
  </div>

  <div v-else class="space-y-2">
    <div v-for="i in count" :key="i" class="flex items-center gap-3 py-2.5 px-3 border border-default rounded-lg">
      <USkeleton class="size-4 rounded-full shrink-0" />
      <USkeleton class="h-4 flex-1 max-w-xs" />
    </div>
  </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{ variant?: 'list' | 'stat' | 'card'; count?: number }>(), {
  variant: 'list',
  count: 3,
})
</script>
