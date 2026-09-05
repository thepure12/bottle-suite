<template>
  <div class="flex items-center" :class="gap">
    <span class="rounded-full bg-primary shrink-0" :class="dotSize" aria-hidden="true" />
    <span class="font-semibold text-highlighted" :class="textSize">Bottle Suite</span>
  </div>
</template>

<script setup lang="ts">
const props = withDefaults(defineProps<{ size?: 'sm' | 'lg' }>(), { size: 'sm' })

const dotSize = computed(() => (props.size === 'lg' ? 'size-3' : 'size-2.5'))
const textSize = computed(() => (props.size === 'lg' ? 'text-lg' : ''))
const gap = computed(() => (props.size === 'lg' ? 'gap-2.5' : 'gap-2'))
</script>
