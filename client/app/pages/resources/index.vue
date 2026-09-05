<template>
  <div class="space-y-6">
    <PageHeader title="DB Resources" description="Tables exposed as REST resources.">
      <template #actions>
        <UButton icon="i-lucide-circle-plus" @click="dialogAdd = true">Add resource</UButton>
      </template>
    </PageHeader>

    <LoadingRows v-if="loading" variant="list" :count="4" />
    <div v-else-if="resources.length" class="space-y-2">
      <NuxtLink
        v-for="r in resources"
        :key="r.name"
        :to="`/resources/${r.id}`"
        class="flex items-center gap-3 py-3 px-3 border border-default rounded-lg hover:bg-elevated transition-colors"
      >
        <UIcon name="i-lucide-table-2" class="size-4 text-muted shrink-0" />
        <span class="font-mono text-sm flex-1">{{ r.name }}</span>
        <UIcon name="i-lucide-chevron-right" class="size-4 text-dimmed shrink-0" />
      </NuxtLink>
    </div>
    <EmptyState v-else icon="i-lucide-package-open" message="No resources yet. Add one to get started.">
      <template #action>
        <UButton icon="i-lucide-circle-plus" variant="soft" size="sm" @click="dialogAdd = true">Add resource</UButton>
      </template>
    </EmptyState>

    <UModal v-model:open="dialogAdd" title="Add Resource">
      <template #body>
        <UFormField label="Name">
          <UInput v-model="newResourceName" class="w-full" />
        </UFormField>
      </template>
      <template #footer>
        <UButton color="neutral" variant="ghost" @click="dialogAdd = false">Cancel</UButton>
        <UButton :loading="saving" @click="save">Save</UButton>
      </template>
    </UModal>
  </div>
</template>

<script setup lang="ts">
definePageMeta({ title: 'DB Resources' })

const { resources, fetchResources, addResource } = useResourcesStore()
const { showError } = useToastError()

const loading = ref(false)
const dialogAdd = ref(false)
const newResourceName = ref('')
const saving = ref(false)

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
</script>
