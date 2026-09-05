<template>
  <ClientOnly>
    <RedocViewer />
    <template #fallback>
      <div class="nuxt-redoc-loading">Loading API docs…</div>
    </template>
  </ClientOnly>
</template>

<style scoped>
.nuxt-redoc-loading {
  padding: 2rem;
  font-family: -apple-system, BlinkMacSystemFont, sans-serif;
  color: #666;
}
</style>
