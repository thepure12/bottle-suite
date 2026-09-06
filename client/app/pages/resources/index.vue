<template>
  <div class="space-y-6">
    <PageHeader title="DB Resources" description="Tables exposed as REST resources.">
      <template #actions>
        <UButton icon="i-lucide-circle-plus" @click="dialogAdd = true">Add resource</UButton>
      </template>
    </PageHeader>

    <UInput
      v-if="resources.length"
      v-model="query"
      icon="i-lucide-search"
      placeholder="Filter resources..."
      class="w-full max-w-sm"
    />

    <LoadingRows v-if="loading" variant="list" :count="4" />
    <div v-else-if="filteredResources.length" class="space-y-2">
      <div
        v-for="r in filteredResources"
        :key="r.name"
        class="flex items-center gap-3 py-3 px-3 border border-default rounded-lg hover:bg-elevated transition-colors"
      >
        <NuxtLink :to="`/resources/${r.id}`" class="flex items-center gap-3 flex-1 min-w-0">
          <UIcon name="i-lucide-table-2" class="size-4 text-muted shrink-0" />
          <span class="font-mono text-sm flex-1 truncate">{{ r.name }}</span>
        </NuxtLink>
        <UButton
          icon="i-lucide-trash-2"
          color="error"
          variant="ghost"
          size="xs"
          aria-label="Delete"
          @click="openDelete(r)"
        />
        <NuxtLink :to="`/resources/${r.id}`">
          <UIcon name="i-lucide-chevron-right" class="size-4 text-dimmed shrink-0" />
        </NuxtLink>
      </div>
    </div>
    <EmptyState
      v-else-if="resources.length"
      icon="i-lucide-search"
      message="No resources match your search."
    />
    <EmptyState v-else icon="i-lucide-package-open" message="No resources yet. Add one to get started.">
      <template #action>
        <UButton icon="i-lucide-circle-plus" variant="soft" size="sm" @click="dialogAdd = true">Add resource</UButton>
      </template>
    </EmptyState>

    <UModal v-model:open="dialogAdd" title="Add Resource">
      <template #body>
        <UFormField label="Name" :error="nameError">
          <UInput v-model="newResourceName" class="w-full" />
        </UFormField>
      </template>
      <template #footer>
        <UButton color="neutral" variant="ghost" @click="dialogAdd = false">Cancel</UButton>
        <UButton :disabled="!!nameError || !newResourceName" :loading="saving" @click="save">Save</UButton>
      </template>
    </UModal>

    <ConfirmDialog
      v-model:open="deleteDialogOpen"
      title="Delete this resource?"
      :message="deleteMessage"
      :loading="deleting"
      @confirm="confirmDelete"
    />
  </div>
</template>

<script setup lang="ts">
definePageMeta({ title: 'DB Resources' })

const { resources, fetchResources, addResource, deleteResource } = useResourcesStore()
const { showError, showSuccess } = useToastError()

const loading = ref(false)
const dialogAdd = ref(false)
const newResourceName = ref('')
const saving = ref(false)
const query = ref('')

const filteredResources = computed(() => (
  resources.value.filter(r => r.name.toLowerCase().includes(query.value.toLowerCase()))
))

const nameError = computed(() => {
  if (!newResourceName.value) return undefined
  return isValidResourceName(newResourceName.value)
    ? undefined
    : 'Must be snake_case (lowercase letters, numbers, underscores; cannot start with a digit).'
})

onMounted(async () => {
  loading.value = true
  try {
    await fetchResources()
  } catch (e: any) {
    showError(e?.data?.message ?? 'Failed to load resources')
  } finally {
    loading.value = false
  }
})

async function save() {
  saving.value = true
  try {
    await addResource(newResourceName.value)
    newResourceName.value = ''
    dialogAdd.value = false
  } catch (e: any) {
    showError(e?.data?.message ?? 'Failed to add resource')
  } finally {
    saving.value = false
  }
}

const deleteDialogOpen = ref(false)
const deleting = ref(false)
const pendingDelete = ref<{ id: string; name: string } | null>(null)

const deleteMessage = computed(() => (
  pendingDelete.value ? `Table "${pendingDelete.value.name}" and all its rows will be permanently deleted.` : ''
))

function openDelete(r: { id: string; name: string }) {
  pendingDelete.value = r
  deleteDialogOpen.value = true
}

async function confirmDelete() {
  if (!pendingDelete.value) return
  deleting.value = true
  try {
    await deleteResource(pendingDelete.value.id)
    deleteDialogOpen.value = false
    showSuccess('Deleted')
  } catch (e: any) {
    showError(e?.data?.message ?? 'Failed to delete')
  } finally {
    deleting.value = false
  }
}
</script>
