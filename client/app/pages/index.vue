<template>
  <div class="space-y-6">
    <PageHeader title="Overview" description="A snapshot of this Bottle Suite server." />

    <LoadingRows v-if="loading" variant="stat" :count="3" />
    <div v-else class="grid grid-cols-1 sm:grid-cols-3 gap-4">
      <StatCard icon="i-lucide-package" :value="resources.length" label="DB resources" />
      <StatCard icon="i-lucide-database" :value="dbBackend" label="Database backend" />
      <StatCard icon="i-lucide-blocks" :value="`${enabledPlugins.length}/${plugins.length}`" label="Plugins enabled" />
    </div>

    <div>
      <h2 class="text-sm font-medium text-muted mb-2">Plugins</h2>
      <LoadingRows v-if="loading" variant="card" :count="6" />
      <div v-else class="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div
          v-for="p in plugins"
          :key="p.key"
          class="flex items-center gap-3 border border-default rounded-lg p-4"
        >
          <span class="font-mono text-sm flex-1">{{ p.label }}</span>
          <UBadge :color="p.enabled ? 'success' : 'neutral'" variant="subtle" size="sm">
            {{ p.enabled ? 'Enabled' : 'Disabled' }}
          </UBadge>
        </div>
      </div>
    </div>

    <div v-if="!loading && resources.length === 0" class="flex justify-start">
      <UButton to="/resources" icon="i-lucide-package">Add your first resource</UButton>
    </div>
  </div>
</template>

<script setup lang="ts">
definePageMeta({ title: 'Overview' })

const { resources, fetchResources } = useResourcesStore()
const { parsed, loading, fetchConfig } = useConfigStore()
const { showError } = useToastError()

onMounted(async () => {
  try {
    await Promise.all([fetchResources(), fetchConfig()])
  } catch (e: any) {
    showError(e?.data?.message ?? 'Failed to load overview')
  }
})

function isEnabled(raw: unknown) {
  return raw !== undefined && raw !== false
}

const dbBackend = computed(() => {
  if (isEnabled(parsed.value.sqlite)) return 'SQLite'
  if (isEnabled(parsed.value.sql)) return 'SQL'
  return 'None'
})

const plugins = computed(() => [
  { key: 'cors', label: 'CORS', enabled: isEnabled(parsed.value.cors) },
  { key: 'rest', label: 'REST', enabled: isEnabled(parsed.value.rest) },
  { key: 'jwt', label: 'JWT', enabled: isEnabled(parsed.value.jwt) },
  { key: 'sqlite', label: 'SQLite', enabled: isEnabled(parsed.value.sqlite) },
  { key: 'sql', label: 'SQL', enabled: isEnabled(parsed.value.sql) },
  { key: 'dashboard', label: 'Dashboard', enabled: isEnabled(parsed.value.dashboard) },
])

const enabledPlugins = computed(() => plugins.value.filter(p => p.enabled))
</script>
