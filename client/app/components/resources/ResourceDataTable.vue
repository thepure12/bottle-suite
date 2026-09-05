<template>
  <div class="space-y-3">
    <UTable :data="pageItems" :columns="columns" :loading="loading">
      <template #empty>
        <EmptyState icon="i-lucide-inbox" :message="emptyMessage">
          <template #action>
            <UButton icon="i-lucide-refresh-cw" variant="soft" size="sm" @click="emit('refresh')">Refresh</UButton>
          </template>
        </EmptyState>
      </template>
    </UTable>
    <div v-if="items.length > pageSize" class="flex justify-end">
      <UPagination v-model:page="page" :total="items.length" :items-per-page="pageSize" />
    </div>
  </div>
</template>

<style scoped>
/* Data values render in mono so they read visually distinct from UI chrome
   (headers/labels stay in the sans font via UTable's own <th> styling). */
:deep(td) {
  font-family: var(--font-mono);
  font-size: 0.8125rem;
}
</style>

<script setup lang="ts">
import { h, resolveComponent } from 'vue'
import type { TableColumn } from '@nuxt/ui'

const props = withDefaults(defineProps<{
  items: Record<string, any>[]
  loading?: boolean
  columnKeys?: string[]
  hiddenColumns?: string[]
  emptyMessage?: string
}>(), {
  emptyMessage: 'No data available. Try refreshing - the server may be reloading.',
})

const emit = defineEmits<{ edit: [item: Record<string, any>]; refresh: [] }>()

const UButton = resolveComponent('UButton')

const page = ref(1)
const pageSize = 20

const pageItems = computed(() => {
  const start = (page.value - 1) * pageSize
  return props.items.slice(start, start + pageSize)
})

watch(() => props.items.length, () => { page.value = 1 })

const columns = computed<TableColumn<Record<string, any>>[]>(() => {
  const allKeys = props.items.length ? Object.keys(props.items[0] ?? {}) : (props.columnKeys ?? [])
  const keys = allKeys.filter(key => !props.hiddenColumns?.includes(key))
  const cols: TableColumn<Record<string, any>>[] = keys.map(key => (key === 'roles'
    ? {
        accessorKey: key,
        header: humanizeKey(key),
        cell: ({ row }) => {
          const v = row.original.roles
          if (v === true) return 'Any token'
          if (Array.isArray(v)) return v.length ? v.join(', ') : 'Public'
          return 'Public'
        },
      }
    : {
        accessorKey: key,
        header: humanizeKey(key),
      }))
  cols.push({
    id: 'actions',
    header: '',
    cell: ({ row }) => h(UButton, {
      icon: 'i-lucide-pencil',
      color: 'neutral',
      variant: 'ghost',
      size: 'xs',
      onClick: () => emit('edit', row.original),
    }),
  })
  return cols
})
</script>
