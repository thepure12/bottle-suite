<template>
  <div class="space-y-6">
    <PageHeader :title="resourceId" mono />

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
        :show-delete="showDelete"
        :can-delete="canDelete"
        @edit="openEdit"
        @delete="openDelete"
        @refresh="reload"
      />
    </UCard>

    <ResourceEditDialog
      v-model:open="dialogOpen"
      :tab="tab"
      :keys="editedItemKeys"
      :item="editedItem"
      :is-new="isNew"
      :datatypes="datatypes"
      :disabled-keys="disabledKeys"
      :role-options="roleOptions"
      :saving="savingItem"
      @save="onSave"
    />

    <ConfirmDialog
      v-model:open="deleteDialogOpen"
      title="Delete this?"
      :message="deleteMessage"
      :loading="deleting"
      @confirm="confirmDelete"
    />
  </div>
</template>

<script setup lang="ts">
import type { ResourceField } from '~/composables/useResourcesStore'

const TABS = ['Fields', 'Paths', 'Roles', 'Entries'] as const
type TabName = typeof TABS[number]

const route = useRoute()
const router = useRouter()
const { showError, showSuccess } = useToastError()
const {
  resource, entries, datatypes,
  fetchResource, fetchDatatypes, fetchEntries,
  updateResourceAttr, removeResourceAttr, addEntry, updateEntry, deleteEntry,
} = useResourcesStore()

const resourceId = computed(() => route.params.id as string)

const initialHash = route.hash.replace('#', '') as TabName
const tab = ref<TabName>(TABS.includes(initialHash) ? initialHash : 'Fields')
const tabItems = TABS.map(t => ({ label: t, value: t }))

watch(tab, (val) => router.replace({ hash: `#${val}` }))

const loadingResource = ref(false)

async function reload() {
  loadingResource.value = true
  try {
    await fetchResource(resourceId.value)
    await Promise.all([fetchDatatypes(), fetchEntries()])
  } catch (e: any) {
    showError(e?.data?.message ?? 'Failed to load resource')
  } finally {
    loadingResource.value = false
  }
}

onMounted(reload)

const currentItems = computed<Record<string, any>[]>(() => {
  switch (tab.value) {
    case 'Fields': return resource.value?.fields ?? []
    case 'Paths': return resource.value?.paths ?? []
    case 'Roles': return resource.value?.roles ?? []
    case 'Entries': return entries.value
    default: return []
  }
})

const FALLBACK_COLUMNS: Record<Exclude<TabName, 'Entries'>, string[]> = {
  Fields: ['name', 'type', 'notnull', 'default', 'key'],
  Paths: ['path', 'index'],
  Roles: ['method', 'roles'],
}

const fallbackColumns = computed(() => (
  tab.value === 'Entries' ? (resource.value?.fields ?? []).map(f => f.name) : FALLBACK_COLUMNS[tab.value]
))

const emptyMessage = computed(() => (
  tab.value === 'Entries'
    ? 'No entries available. Try refreshing - the server may be reloading.'
    : `No ${tab.value.toLowerCase()} yet - add one to get started.`
))

const primaryKeyName = computed(() => resource.value?.fields.find(f => f.key === 1)?.name)

const disabledKeys = computed(() => {
  const keys = ['method']
  if (tab.value === 'Fields' && !isNew.value) keys.push('type', 'notnull', 'default', 'key')
  if (tab.value === 'Entries' && primaryKeyName.value) keys.push(primaryKeyName.value)
  return keys
})

// Roles are fixed-cardinality (always all 5 HTTP methods) -- nothing to
// remove there. The primary-key field can't be deleted (createResForDB
// requires one; dropping it would break every generated CRUD method).
const showDelete = computed(() => tab.value !== 'Roles')
function canDelete(item: Record<string, any>) {
  return !(tab.value === 'Fields' && item.key === 1)
}

const dialogOpen = ref(false)
const isNew = ref(false)
const editedItem = ref<Record<string, any>>({})
const editedIndex = ref(-1)
const savingItem = ref(false)

const editedItemKeys = computed(() => (
  Object.keys(editedItem.value).filter(k => !(tab.value === 'Paths' && k === 'index'))
))

function openAdd() {
  isNew.value = true
  editedIndex.value = -1
  if (tab.value === 'Fields') {
    editedItem.value = { name: '', type: '', notnull: false, default: '', key: 0 }
  } else if (tab.value === 'Paths') {
    editedItem.value = { path: '', index: resource.value?.paths.length ?? 0 }
  } else if (tab.value === 'Entries') {
    editedItem.value = Object.fromEntries((resource.value?.fields ?? []).map(f => [f.name, '']))
  }
  dialogOpen.value = true
}

function openEdit(item: Record<string, any>) {
  isNew.value = false
  if (tab.value === 'Entries') {
    editedIndex.value = entries.value.indexOf(item)
  } else if (tab.value === 'Fields') {
    editedIndex.value = (resource.value?.fields ?? []).indexOf(item as ResourceField)
  }
  editedItem.value = { ...item }
  dialogOpen.value = true
}

const deleteDialogOpen = ref(false)
const deleting = ref(false)
const pendingDelete = ref<Record<string, any> | null>(null)

const deleteMessage = computed(() => {
  if (!pendingDelete.value) return ''
  if (tab.value === 'Entries') return 'This entry will be permanently deleted.'
  if (tab.value === 'Paths') return `Path "${pendingDelete.value.path}" will be removed.`
  if (tab.value === 'Fields') return `Column "${pendingDelete.value.name}" will be permanently deleted.`
  return 'This will be permanently deleted.'
})

function openDelete(item: Record<string, any>) {
  pendingDelete.value = item
  deleteDialogOpen.value = true
}

async function confirmDelete() {
  if (!pendingDelete.value) return
  deleting.value = true
  try {
    if (tab.value === 'Entries') {
      await deleteEntry(entries.value.indexOf(pendingDelete.value))
    } else if (tab.value === 'Paths') {
      await removeResourceAttr('remove_path', pendingDelete.value.index)
    } else if (tab.value === 'Fields') {
      const cid = (resource.value?.fields ?? []).indexOf(pendingDelete.value as ResourceField)
      await updateResourceAttr('fields', { cid, drop: true })
    }
    deleteDialogOpen.value = false
    showSuccess('Deleted')
  } catch (e: any) {
    showError(e?.data?.message ?? 'Failed to delete')
  } finally {
    deleting.value = false
  }
}

const roleOptions = computed(() => {
  const names = (resource.value?.roles ?? [])
    .flatMap(r => Array.isArray(r.roles) ? r.roles : [])
  return [...new Set(names)]
})

async function onSave(item: Record<string, any>) {
  savingItem.value = true
  try {
    if (tab.value === 'Fields') {
      await updateResourceAttr('fields', {
        cid: isNew.value ? null : editedIndex.value,
        name: item.name,
        type: item.type,
        notnull: item.notnull ? 1 : 0,
        dflt_value: item.default || null,
        pk: item.key,
      })
    } else if (tab.value === 'Paths') {
      await updateResourceAttr('paths', { index: item.index, path: item.path })
    } else if (tab.value === 'Roles') {
      await updateResourceAttr('roles', { method: item.method, roles: item.roles })
    } else if (tab.value === 'Entries') {
      if (isNew.value) await addEntry(item)
      else await updateEntry(item, editedIndex.value)
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
