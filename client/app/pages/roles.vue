<template>
  <div class="space-y-6">
    <PageHeader title="Roles" description="Bulk-edit access roles across every resource." />

    <div class="flex items-center justify-between gap-3">
      <UInput
        v-if="rows.length"
        v-model="query"
        icon="i-lucide-search"
        placeholder="Filter by resource, kind, method or role..."
        class="w-full max-w-sm"
      />
      <UButton
        v-if="selected.length > 1"
        icon="i-lucide-pencil"
        color="neutral"
        variant="soft"
        size="sm"
        @click="openBulkEdit"
      >
        Edit {{ selected.length }} selected
      </UButton>
    </div>

    <LoadingRows v-if="loading" variant="list" :count="6" />
    <ResourceDataTable
      v-else
      v-model:selected="selected"
      :items="filteredRows"
      :column-keys="['resource', 'kind', 'method', 'roles']"
      :hidden-columns="['id']"
      select-key="id"
      selectable
      empty-message="No resources yet."
      @edit="openEdit"
      @refresh="reload"
    />

    <ResourceEditDialog
      v-model:open="dialogOpen"
      tab="Roles"
      :keys="editedItemKeys"
      :item="editedItem"
      :is-new="false"
      :datatypes="[]"
      :disabled-keys="disabledKeys"
      :role-options="roleOptions"
      :bulk-items="bulkItems"
      :saving="saving"
      @save="onSave"
    />
  </div>
</template>

<script setup lang="ts">
definePageMeta({ title: 'Roles' })

const { resources, fetchAllRoles, updateRolesBulk } = useRolesStore()
const { parsed: cfg, fetchConfig } = useConfigStore()
const { showError, showSuccess } = useToastError()

const loading = ref(false)

async function reload() {
  loading.value = true
  try {
    const configPromise = Object.keys(cfg.value).length ? Promise.resolve() : fetchConfig()
    await Promise.all([fetchAllRoles(), configPromise])
  } catch (e: any) {
    showError(e?.data?.message ?? 'Failed to load roles')
  } finally {
    loading.value = false
  }
}

onMounted(reload)

interface RoleRow {
  id: string
  resource: string
  kind: 'db' | 'python'
  method: string
  roles: boolean | string[]
}

const rows = computed<RoleRow[]>(() => resources.value.flatMap(r => (
  r.roles.map(role => ({
    id: `${r.kind}:${r.name}:${role.method}`,
    resource: r.name,
    kind: r.kind,
    method: role.method,
    roles: role.roles,
  }))
)))

const query = ref('')
const filteredRows = computed(() => {
  const q = query.value.toLowerCase()
  if (!q) return rows.value
  return rows.value.filter(row => (
    row.resource.toLowerCase().includes(q)
    || row.kind.includes(q)
    || row.method.includes(q)
    || (Array.isArray(row.roles) && row.roles.some(r => r.toLowerCase().includes(q)))
  ))
})

const globalRoleNames = computed(() => (cfg.value.roles as { names?: string[] } | undefined)?.names ?? [])
const roleOptions = computed(() => {
  const names = rows.value.flatMap(r => Array.isArray(r.roles) ? r.roles : [])
  return [...new Set([...names, ...globalRoleNames.value])]
})

const selected = ref<string[]>([])
const dialogOpen = ref(false)
const saving = ref(false)
const editedItem = ref<Record<string, any>>({})
const bulkItems = ref<{ resource: string; methods: string[] }[]>([])

const editedItemKeys = computed(() => Object.keys(editedItem.value).filter(k => !['kind', 'id'].includes(k)))
const disabledKeys = ['resource', 'method']

function openEdit(item: Record<string, any>) {
  bulkItems.value = []
  editedItem.value = { ...item }
  dialogOpen.value = true
}

function openBulkEdit() {
  const byResource = new Map<string, string[]>()
  for (const row of rows.value) {
    if (!selected.value.includes(row.id)) continue
    byResource.set(row.resource, [...(byResource.get(row.resource) ?? []), row.method])
  }
  bulkItems.value = [...byResource.entries()].map(([resource, methods]) => ({ resource, methods }))
  editedItem.value = { roles: false }
  dialogOpen.value = true
}

async function onSave(item: Record<string, any>) {
  saving.value = true
  try {
    const updates = item.bulkItems
      ? item.bulkItems.map((e: { resource: string; methods: string[] }) => ({
          resource: e.resource, methods: e.methods, roles: item.roles,
        }))
      : [{ resource: item.resource, methods: [item.method], roles: item.roles }]
    await updateRolesBulk(updates)
    selected.value = []
    bulkItems.value = []
    dialogOpen.value = false
    showSuccess('Saved')
  } catch (e: any) {
    showError(e?.data?.message ?? 'Failed to save')
  } finally {
    saving.value = false
  }
}
</script>
