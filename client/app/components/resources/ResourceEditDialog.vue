<template>
  <UModal v-model:open="open" :title="`${isNew ? 'Add' : 'Edit'} ${singular}`">
    <template #body>
      <div class="space-y-4">
        <UFormField v-for="key in keys" :key="key" :label="humanizeKey(key)">
          <USelect
            v-if="key === 'type' && tab === 'Fields'"
            v-model="localItem[key]"
            :items="datatypes"
            :disabled="disabledKeys.includes(key)"
            class="w-full font-mono"
          />
          <USwitch
            v-else-if="key === 'notnull'"
            v-model="notnullBool"
            :disabled="disabledKeys.includes(key)"
          />
          <div v-else-if="key === 'roles' && tab === 'Roles'" class="space-y-2">
            <USelect v-model="roleMode" :items="roleModeItems" class="w-full" />
            <USelectMenu
              v-if="roleMode === 'roles'"
              v-model="roleList"
              multiple
              create-item
              :items="localRoleOptions"
              placeholder="Select or type to add a role"
              class="w-full font-mono"
              @create="onCreateRole"
            />
          </div>
          <UInput
            v-else
            v-model="localItem[key]"
            :disabled="disabledKeys.includes(key)"
            class="w-full font-mono"
          />
        </UFormField>
      </div>
    </template>
    <template #footer>
      <UButton color="neutral" variant="ghost" @click="open = false">Cancel</UButton>
      <UButton :loading="saving" @click="save">Save</UButton>
    </template>
  </UModal>
</template>

<script setup lang="ts">
const open = defineModel<boolean>('open', { required: true })

const props = defineProps<{
  tab: 'Fields' | 'Paths' | 'Roles' | 'Entries'
  keys: string[]
  item: Record<string, any>
  isNew: boolean
  datatypes: string[]
  disabledKeys: string[]
  roleOptions?: string[]
  saving?: boolean
}>()

const emit = defineEmits<{ save: [item: Record<string, any>] }>()

const singular = computed(() => props.tab.replace(/s$/, ''))

const localItem = reactive<Record<string, any>>({})
watch(() => props.item, (val) => {
  for (const key of Object.keys(localItem)) delete localItem[key]
  Object.assign(localItem, val)
}, { immediate: true, deep: true })

const notnullBool = computed({
  get: () => !!localItem.notnull,
  set: (v: boolean) => { localItem.notnull = v ? 1 : 0 },
})

const roleModeItems = [
  { label: 'Public (no auth required)', value: 'public' },
  { label: 'Any token', value: 'any' },
  { label: 'Specific roles', value: 'roles' },
]
const localRoleOptions = ref<string[]>([])

watch(() => props.roleOptions, (v) => { localRoleOptions.value = [...(v ?? [])] }, { immediate: true })

const roleMode = computed<'public' | 'any' | 'roles'>({
  get: () => localItem.roles === true ? 'any' : Array.isArray(localItem.roles) ? 'roles' : 'public',
  set: (mode) => {
    localItem.roles = mode === 'public' ? false : mode === 'any' ? true : [...roleList.value]
  },
})

const roleList = computed<string[]>({
  get: () => Array.isArray(localItem.roles) ? [...localItem.roles] : [],
  set: (val) => { localItem.roles = [...val] },
})

function onCreateRole(item: string) {
  if (!localRoleOptions.value.includes(item)) localRoleOptions.value.push(item)
  if (!roleList.value.includes(item)) roleList.value = [...roleList.value, item]
}

function save() {
  emit('save', { ...localItem })
}
</script>
