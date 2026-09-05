<template>
  <ClientOnly>
    <SwaggerUIViewer />
    <template #fallback>
      <div class="nuxt-swagger-ui-loading">Loading API explorer…</div>
    </template>
  </ClientOnly>
</template>

<style scoped>
.nuxt-swagger-ui-loading {
  padding: 2rem;
  font-family: -apple-system, BlinkMacSystemFont, sans-serif;
  color: #666;
}
</style>
