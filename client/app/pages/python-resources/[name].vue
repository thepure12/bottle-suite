<template>
  <div class="space-y-6">
    <PageHeader :title="resourceName" mono />

    <UCard>
      <template #header>
        <div class="flex items-center justify-between">
          <UTabs v-model="tab" :items="tabItems" />
          <UButton
            v-if="tab !== 'Roles'"
            icon="i-lucide-circle-plus"
            color="neutral"
            variant="ghost"
            aria-label="Add"
            @click="openAdd"
          />
        </div>
      </template>

      <ResourceDataTable
        :items="currentItems"
        :loading="loadingResource"
        :column-keys="fallbackColumns"
        :hidden-columns="tab === 'Paths' ? ['index'] : []"
        :empty-message="emptyMessage"
        @edit="openEdit"
        @refresh="reload"
      />
    </UCard>

    <ResourceEditDialog
      v-model:open="dialogOpen"
      :tab="tab"
      :keys="editedItemKeys"
      :item="editedItem"
      :is-new="isNew"
      :datatypes="[]"
      :disabled-keys="disabledKeys"
      :role-options="roleOptions"
      :saving="savingItem"
      @save="onSave"
    />
  </div>
</template>

<script setup lang="ts">
const TABS = ['Paths', 'Roles'] as const
type TabName = typeof TABS[number]

const route = useRoute()
const router = useRouter()
const { showError, showSuccess } = useToastError()
const { resource, fetchPythonResource, updateResourceAttr } = usePythonResourcesStore()

const resourceName = computed(() => route.params.name as string)

const initialHash = route.hash.replace('#', '') as TabName
const tab = ref<TabName>(TABS.includes(initialHash) ? initialHash : 'Paths')
const tabItems = TABS.map(t => ({ label: t, value: t }))

watch(tab, (val) => router.replace({ hash: `#${val}` }))

const loadingResource = ref(false)

async function reload() {
  loadingResource.value = true
  try {
    await fetchPythonResource(resourceName.value)
  } catch (e: any) {
    showError(e?.data?.message ?? 'Failed to load resource')
  } finally {
    loadingResource.value = false
  }
}

onMounted(reload)

const currentItems = computed<Record<string, any>[]>(() => {
  switch (tab.value) {
    case 'Paths': return resource.value?.paths ?? []
    case 'Roles': return resource.value?.roles ?? []
    default: return []
  }
})

const FALLBACK_COLUMNS: Record<TabName, string[]> = {
  Paths: ['path', 'index'],
  Roles: ['method', 'roles'],
}

const fallbackColumns = computed(() => FALLBACK_COLUMNS[tab.value])

const emptyMessage = computed(() => `No ${tab.value.toLowerCase()} yet - add one to get started.`)

const disabledKeys = computed(() => ['method'])

const roleOptions = computed(() => {
  const names = (resource.value?.roles ?? [])
    .flatMap(r => Array.isArray(r.roles) ? r.roles : [])
  return [...new Set(names)]
})

const dialogOpen = ref(false)
const isNew = ref(false)
const editedItem = ref<Record<string, any>>({})
const savingItem = ref(false)

const editedItemKeys = computed(() => (
  Object.keys(editedItem.value).filter(k => !(tab.value === 'Paths' && k === 'index'))
))

function openAdd() {
  isNew.value = true
  if (tab.value === 'Paths') {
    editedItem.value = { path: '', index: resource.value?.paths.length ?? 0 }
  }
  dialogOpen.value = true
}

function openEdit(item: Record<string, any>) {
  isNew.value = false
  editedItem.value = { ...item }
  dialogOpen.value = true
}

async function onSave(item: Record<string, any>) {
  savingItem.value = true
  try {
    if (tab.value === 'Paths') {
      await updateResourceAttr('paths', { index: item.index, path: item.path })
    } else if (tab.value === 'Roles') {
      await updateResourceAttr('roles', { method: item.method, roles: item.roles })
    }
    dialogOpen.value = false
    showSuccess('Saved')
  } catch (e: any) {
    showError(e?.data?.message ?? 'Failed to save')
  } finally {
    savingItem.value = false
  }
}
</script>
