<template>
  <UApp>
    <BrandScreen>
      <UCard>
        <div class="flex flex-col items-center text-center gap-3 py-2">
          <UIcon name="i-lucide-triangle-alert" class="size-8 text-primary" />
          <h1 class="text-lg font-semibold text-highlighted">
            {{ error?.statusCode === 404 ? 'Page not found' : 'Something went wrong loading this page' }}
          </h1>
          <p v-if="error?.message" class="text-sm text-muted">{{ error.message }}</p>
          <UButton to="/" class="mt-2" @click="handleError">Back to overview</UButton>
        </div>
      </UCard>
    </BrandScreen>
  </UApp>
</template>

<script setup lang="ts">
const { error } = defineProps<{ error: { statusCode: number; message: string } }>()

function handleError() {
  clearError({ redirect: '/' })
}
</script>
