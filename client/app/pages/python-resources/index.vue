<template>
  <div class="space-y-6">
    <PageHeader title="Python Resources" description="Scaffold new Resource classes under resources/.">
      <template #actions>
        <UButton icon="i-lucide-circle-plus" @click="dialogAdd = true">Add resource</UButton>
      </template>
    </PageHeader>

    <LoadingRows v-if="loading" variant="list" :count="4" />
    <div v-else-if="resources.length" class="space-y-2">
      <NuxtLink
        v-for="r in resources"
        :key="r.name"
        :to="`/python-resources/${r.name}`"
        class="flex items-center gap-3 py-3 px-3 border border-default rounded-lg hover:bg-elevated transition-colors"
      >
        <UIcon name="i-lucide-file-code-2" class="size-4 text-muted shrink-0" />
        <span class="font-mono text-sm flex-1">{{ r.name }}</span>
        <span class="font-mono text-xs text-dimmed shrink-0">resources/{{ r.name }}.py</span>
        <UIcon name="i-lucide-chevron-right" class="size-4 text-dimmed shrink-0" />
      </NuxtLink>
    </div>
    <EmptyState v-else icon="i-lucide-file-code-2" message="No Python resources yet. Add one to get started.">
      <template #action>
        <UButton icon="i-lucide-circle-plus" variant="soft" size="sm" @click="dialogAdd = true">Add resource</UButton>
      </template>
    </EmptyState>

    <UModal v-model:open="dialogAdd" title="Add Python Resource">
      <template #body>
        <UFormField label="Name" description="Used as the module filename and route (snake_case).">
          <UInput v-model="newResourceName" class="w-full" placeholder="my_resource" />
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
definePageMeta({ title: 'Python Resources' })

const { resources, fetchPythonResources, createPythonResource } = usePythonResourcesStore()
const { showError, showSuccess } = useToastError()

const loading = ref(false)
const dialogAdd = ref(false)
const newResourceName = ref('')
const saving = ref(false)

onMounted(async () => {
  loading.value = true
  try {
    await fetchPythonResources()
  } catch (e: any) {
    showError(e?.data?.message ?? 'Failed to load resources')
  } finally {
    loading.value = false
  }
})

async function save() {
  saving.value = true
  try {
    const created = await createPythonResource(newResourceName.value)
    showSuccess(`Created resources/${created.name}.py -- add your logic there.`)
    newResourceName.value = ''
    dialogAdd.value = false
  } catch (e: any) {
    showError(e?.data?.message ?? 'Failed to add resource')
  } finally {
    saving.value = false
  }
}
</script>
