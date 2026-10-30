<template>
  <UModal v-model:open="open" :title="dialogTitle">
    <template #body>
      <div class="space-y-4">
        <div v-if="bulkItems?.length || bulkMethods?.length" class="space-y-1">
          <p class="text-sm text-muted">Editing roles for:</p>
          <div class="flex flex-wrap gap-1">
            <template v-if="bulkItems?.length">
              <UBadge v-for="entry in bulkItems" :key="entry.resource" color="neutral" variant="subtle" class="font-mono">
                {{ entry.resource }}: {{ entry.methods.join(', ').toUpperCase() }}
              </UBadge>
            </template>
            <template v-else>
              <UBadge v-for="m in bulkMethods" :key="m" color="neutral" variant="subtle" class="uppercase">
                {{ m }}
              </UBadge>
            </template>
          </div>
        </div>
        <UFormField v-for="key in visibleKeys" :key="key" :label="humanizeKey(key)">
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
  bulkMethods?: string[]
  bulkItems?: { resource: string; methods: string[] }[]
  saving?: boolean
}>()

const emit = defineEmits<{ save: [item: Record<string, any>] }>()

const singular = computed(() => props.tab.replace(/s$/, ''))
const dialogTitle = computed(() => {
  if (props.bulkItems?.length) {
    const methodCount = props.bulkItems.reduce((sum, e) => sum + e.methods.length, 0)
    return `Edit Roles (${props.bulkItems.length} resources, ${methodCount} methods)`
  }
  if (props.bulkMethods?.length) return `Edit Roles (${props.bulkMethods.length} methods)`
  return `${props.isNew ? 'Add' : 'Edit'} ${singular.value}`
})
// Bulk edits apply one role set to several methods (optionally spanning
// several resources) at once -- the resource/method fields don't apply,
// they're replaced by the bulkItems/bulkMethods summary above.
const visibleKeys = computed(() => props.keys.filter((k) => {
  if (props.bulkItems?.length) return !['resource', 'method'].includes(k)
  if (props.bulkMethods?.length) return k !== 'method'
  return true
}))

const localItem = reactive<Record<string, any>>({})
// An empty role list turns the method off: the server registers no route.
// So 'roles' mode with nothing picked yet needs its own flag to stay shown.
const pickingRoles = ref(false)
watch(() => props.item, (val) => {
  for (const key of Object.keys(localItem)) delete localItem[key]
  Object.assign(localItem, val)
  pickingRoles.value = false
}, { immediate: true, deep: true })

const notnullBool = computed({
  get: () => !!localItem.notnull,
  set: (v: boolean) => { localItem.notnull = v ? 1 : 0 },
})

const roleModeItems = [
  { label: 'Public (no auth required)', value: 'public' },
  { label: 'Any token', value: 'any' },
  { label: 'Specific roles', value: 'roles' },
  { label: 'Off (no route)', value: 'off' },
]
const localRoleOptions = ref<string[]>([])

watch(() => props.roleOptions, (v) => { localRoleOptions.value = [...(v ?? [])] }, { immediate: true })

const roleMode = computed<'public' | 'any' | 'roles' | 'off'>({
  get: () => {
    if (localItem.roles === true) return 'any'
    if (!Array.isArray(localItem.roles)) return 'public'
    return localItem.roles.length || pickingRoles.value ? 'roles' : 'off'
  },
  set: (mode) => {
    pickingRoles.value = mode === 'roles'
    localItem.roles = mode === 'public' ? false : mode === 'any' ? true : mode === 'off' ? [] : [...roleList.value]
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
  if (props.bulkItems?.length) {
    emit('save', { roles: localItem.roles, bulkItems: props.bulkItems })
  } else if (props.bulkMethods?.length) {
    emit('save', { roles: localItem.roles, methods: props.bulkMethods })
  } else {
    emit('save', { ...localItem })
  }
}
</script>
