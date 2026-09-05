<template>
  <div class="space-y-4">
    <div v-if="visibleFields.length" class="space-y-4">
      <UFormField v-for="field in visibleFields" :key="field.key" :label="field.label">
        <div class="flex items-center gap-2">
          <USwitch v-if="field.type === 'boolean'" :model-value="known[field.key] === 'true'" @update:model-value="(v: boolean) => known[field.key] = String(v)" />
          <UInput
            v-else
            v-model="known[field.key]"
            :type="field.type ?? 'text'"
            class="w-full font-mono"
          />
          <UButton icon="i-lucide-x" color="neutral" variant="ghost" aria-label="Remove" @click="removeField(field.key)" />
        </div>
      </UFormField>
    </div>

    <UDropdownMenu v-if="remainingFields.length" :items="dropdownItems">
      <UButton icon="i-lucide-plus" color="neutral" variant="soft" size="sm">
        Add field
      </UButton>
    </UDropdownMenu>

    <div v-if="extra.length" class="space-y-2">
      <p class="text-sm text-muted">Unrecognized fields</p>
      <div v-for="(row, i) in extra" :key="i" class="flex gap-2 items-center">
        <UInput v-model="row.key" placeholder="key" class="w-1/3 font-mono" disabled />
        <UInput v-model="row.value" placeholder="value" class="flex-1 font-mono" />
        <UButton icon="i-lucide-x" color="neutral" variant="ghost" aria-label="Remove" @click="extra.splice(i, 1)" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { FieldDef, KeyValueRow } from '~/composables/useConfigStore'

const props = defineProps<{ fields: FieldDef[] }>()

const known = defineModel<Record<string, string>>('known', { required: true })
const extra = defineModel<KeyValueRow[]>('extra', { required: true })

const addedKeys = ref<Set<string>>(new Set())

watch(
  known,
  (val) => {
    for (const field of props.fields) {
      if (val[field.key] !== undefined && val[field.key] !== '') {
        addedKeys.value.add(field.key)
      }
    }
  },
  { immediate: true, deep: true },
)

const visibleFields = computed(() => props.fields.filter(f => addedKeys.value.has(f.key)))
const remainingFields = computed(() => props.fields.filter(f => !addedKeys.value.has(f.key)))

const dropdownItems = computed(() =>
  remainingFields.value.map(field => ({
    label: field.label,
    onSelect: () => addField(field),
  })),
)

function addField(field: FieldDef) {
  addedKeys.value.add(field.key)
  known.value[field.key] = field.default ?? (field.type === 'boolean' ? 'false' : '')
}

function removeField(key: string) {
  addedKeys.value.delete(key)
  known.value[key] = ''
}
</script>
