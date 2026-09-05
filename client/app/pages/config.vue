<template>
  <div class="space-y-6">
    <PageHeader title="Config" description="Bottle Suite server configuration.">
      <template #badge>
        <UBadge v-if="isDirty" color="warning" variant="subtle" size="sm">Unsaved changes</UBadge>
      </template>
      <template #actions>
        <UButton icon="i-lucide-save" :disabled="!isDirty" :loading="saving" @click="save">Save</UButton>
      </template>
    </PageHeader>

    <template v-if="loading">
      <LoadingRows variant="list" :count="3" />
      <LoadingRows variant="card" :count="3" />
    </template>
    <template v-else>
      <UCard>
        <div class="divide-y divide-default">
          <ConfigBooleanSection v-model="cors" label="CORS" icon="i-lucide-globe" description="Add CORS headers so browsers can call this API from another origin/domain" />
          <ConfigBooleanSection v-model="rest" label="REST" icon="i-lucide-route" description="Auto-register your Resource classes and DB tables as REST endpoints" />
          <ConfigBooleanSection v-model="dashboard" label="Dashboard" icon="i-lucide-layout-dashboard" description="Serve this dashboard. Disabling it will lock you out after saving." />
        </div>
      </UCard>

      <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 items-start">
        <ConfigPluginSection
          v-model="jwt"
          label="JWT"
          description="Issue and verify JWT bearer tokens; adds /token and /users/current endpoints"
          icon="i-lucide-key-round"
          :known-fields="[{ key: 'jwt_key', label: 'JWT Key' }]"
          :optional-fields="jwtOptionalFields"
        />
        <ConfigPluginSection
          v-model="sqlite"
          label="SQLite"
          description="Give resources a db cursor backed by a local SQLite file"
          icon="i-lucide-database"
          :known-fields="[{ key: 'database', label: 'Database path' }]"
          :optional-fields="sqliteOptionalFields"
        />
        <ConfigPluginSection
          v-model="sql"
          label="SQL"
          description="Give resources a db cursor backed by a MySQL server"
          icon="i-lucide-server"
          :known-fields="[
            { key: 'host', label: 'Host' },
            { key: 'port', label: 'Port', type: 'number' },
            { key: 'user', label: 'User' },
            { key: 'password', label: 'Password', type: 'password' },
            { key: 'database', label: 'Database' },
          ]"
          :optional-fields="sqlOptionalFields"
        />
      </div>
    </template>

    <UModal v-model:open="confirmDisableOpen" title="Disable the dashboard?">
      <template #body>
        <p class="text-sm text-muted">
          Disabling the dashboard will lock you out of this page after the server reloads. Continue?
        </p>
      </template>
      <template #footer>
        <UButton color="neutral" variant="ghost" @click="confirmDisableOpen = false">Cancel</UButton>
        <UButton color="error" :loading="saving" @click="confirmDisableAndSave">Disable and save</UButton>
      </template>
    </UModal>
  </div>
</template>

<script setup lang="ts">
import { sectionFromToml, sectionToToml, type PluginSection, type FieldDef } from '~/composables/useConfigStore'

definePageMeta({ title: 'Config' })

const { parsed, loading, fetchConfig, saveConfig } = useConfigStore()
const { showError, showSuccess } = useToastError()

const jwtOptionalFields: FieldDef[] = [
  { key: 'token_path', label: 'Token path', default: 'token' },
  { key: 'alg', label: 'Algorithm', default: 'HS256' },
  { key: 'fail_redirect', label: 'Fail redirect', default: '/login' },
  { key: 'debug', label: 'Debug logging', type: 'boolean', default: 'false' },
]
const sqliteOptionalFields: FieldDef[] = [
  { key: 'dictrows', label: 'Return rows as dicts', type: 'boolean', default: 'true' },
]
const sqlOptionalFields: FieldDef[] = [
  { key: 'dictrows', label: 'Return rows as dicts', type: 'boolean', default: 'true' },
]

const cors = ref(false)
const rest = ref(false)
const dashboard = ref(false)
const jwt = ref<PluginSection>({ enabled: false, known: {}, extra: [] })
const sqlite = ref<PluginSection>({ enabled: false, known: {}, extra: [] })
const sql = ref<PluginSection>({ enabled: false, known: {}, extra: [] })
const saving = ref(false)
const confirmDisableOpen = ref(false)
const savedSnapshot = ref('')

function formSnapshot() {
  return JSON.stringify({ cors: cors.value, rest: rest.value, dashboard: dashboard.value, jwt: jwt.value, sqlite: sqlite.value, sql: sql.value })
}

const isDirty = computed(() => formSnapshot() !== savedSnapshot.value)

function loadFromParsed() {
  cors.value = !!parsed.value.cors
  rest.value = !!parsed.value.rest
  dashboard.value = !!parsed.value.dashboard
  jwt.value = sectionFromToml(parsed.value.jwt, ['jwt_key', ...jwtOptionalFields.map(f => f.key)], 'jwt_key')
  sqlite.value = sectionFromToml(parsed.value.sqlite, ['database', ...sqliteOptionalFields.map(f => f.key)], 'database')
  sql.value = sectionFromToml(parsed.value.sql, ['host', 'port', 'user', 'password', 'database', ...sqlOptionalFields.map(f => f.key)], 'database')
  savedSnapshot.value = formSnapshot()
}

onMounted(async () => {
  try {
    await fetchConfig()
    loadFromParsed()
  } catch (e: any) {
    showError(e?.data?.message ?? 'Failed to load config')
  }
})

onBeforeRouteLeave(() => {
  if (!isDirty.value) return true
  return window.confirm('You have unsaved config changes. Leave without saving?')
})

function onBeforeUnload(e: BeforeUnloadEvent) {
  if (!isDirty.value) return
  e.preventDefault()
}

onMounted(() => window.addEventListener('beforeunload', onBeforeUnload))
onBeforeUnmount(() => window.removeEventListener('beforeunload', onBeforeUnload))

function save() {
  if (dashboard.value === false) {
    confirmDisableOpen.value = true
    return
  }
  doSave()
}

async function confirmDisableAndSave() {
  await doSave()
  confirmDisableOpen.value = false
}

async function doSave() {
  saving.value = true
  try {
    parsed.value = {
      ...parsed.value,
      cors: cors.value,
      rest: rest.value,
      dashboard: dashboard.value,
      jwt: sectionToToml(jwt.value, 'jwt_key'),
      sqlite: sectionToToml(sqlite.value, 'database'),
      sql: sectionToToml(sql.value, 'database'),
    }
    await saveConfig()
    savedSnapshot.value = formSnapshot()
    showSuccess('Config saved')
  } catch (e: any) {
    showError(e?.data?.message ?? 'Failed to save config')
  } finally {
    saving.value = false
  }
}
</script>
