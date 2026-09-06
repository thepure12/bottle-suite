<template>
  <UDashboardGroup>
    <UDashboardSearch :groups="commandGroups" :color-mode="false" />

    <UDashboardSidebar collapsible>
      <template #header>
        <BrandMark />
      </template>
      <UNavigationMenu orientation="vertical" :items="navItems" />
    </UDashboardSidebar>

    <UDashboardPanel>
      <template #header>
        <UDashboardNavbar>
          <template #title>
            <UBreadcrumb :items="breadcrumb" />
          </template>
          <template #right>
            <UDashboardSearchButton />
            <UColorModeButton />
            <UButton
              icon="i-lucide-log-out"
              color="neutral"
              variant="ghost"
              aria-label="Logout"
              @click="logout"
            />
          </template>
        </UDashboardNavbar>
      </template>
      <template #body>
        <slot />
      </template>
    </UDashboardPanel>
  </UDashboardGroup>
</template>

<script setup lang="ts">
const { logout } = useAuth()
const route = useRoute()
const { resources, fetchResources } = useResourcesStore()
const { resources: pythonResources, fetchPythonResources } = usePythonResourcesStore()

const NAV_ITEMS = [
  { label: 'Overview', icon: 'i-lucide-layout-grid', to: '/' },
  { label: 'DB Resources', icon: 'i-lucide-package', to: '/resources' },
  { label: 'Python Resources', icon: 'i-lucide-file-code-2', to: '/python-resources' },
  { label: 'API Explorer', icon: 'i-lucide-flask-conical', to: '/api-explorer' },
  { label: 'Config', icon: 'i-lucide-settings', to: '/config' },
]
const navItems = [NAV_ITEMS]

// Resource detail routes (/resources/<id>, /python-resources/<name>) get a
// "DB Resources > <id>" / "Python Resources > <name>" trail; every other
// page just shows its own definePageMeta({ title }).
const breadcrumb = computed(() => {
  if (route.path.startsWith('/resources/')) {
    return [
      { label: 'DB Resources', icon: 'i-lucide-package', to: '/resources' },
      { label: route.params.id as string },
    ]
  }
  if (route.path.startsWith('/python-resources/')) {
    return [
      { label: 'Python Resources', icon: 'i-lucide-file-code-2', to: '/python-resources' },
      { label: route.params.name as string },
    ]
  }
  return [{ label: (route.meta.title as string) ?? 'Overview' }]
})

// Feeds the Cmd/Ctrl+K palette. Resource names are only known once fetched,
// so warm the shared store here rather than requiring every page to do it.
const commandGroups = computed(() => [
  {
    id: 'navigate',
    label: 'Navigate',
    items: NAV_ITEMS.map(item => ({ label: item.label, icon: item.icon, to: item.to })),
  },
  {
    id: 'resources',
    label: 'Resources',
    items: resources.value.map(r => ({ label: r.name, icon: 'i-lucide-table-2', to: `/resources/${r.id}` })),
  },
  {
    id: 'python-resources',
    label: 'Python Resources',
    items: pythonResources.value.map(r => ({ label: r.name, icon: 'i-lucide-file-code-2', to: `/python-resources/${r.name}` })),
  },
])

onMounted(() => {
  if (!resources.value.length) {
    fetchResources().catch(() => {
      // Ignore here - the resources page itself surfaces load failures.
    })
  }
  if (!pythonResources.value.length) {
    fetchPythonResources().catch(() => {
      // Ignore here - the python-resources page itself surfaces load failures.
    })
  }
})
</script>
