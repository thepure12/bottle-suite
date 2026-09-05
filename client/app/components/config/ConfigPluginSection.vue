<template>
  <UCard>
    <template #header>
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-3">
          <UIcon v-if="icon" :name="icon" class="size-5 text-muted shrink-0" />
          <div>
            <p class="font-medium">{{ label }}</p>
            <p v-if="description" class="text-sm text-muted">{{ description }}</p>
          </div>
        </div>
        <div class="flex items-center gap-3">
          <UBadge :color="section.enabled ? 'success' : 'neutral'" variant="subtle" size="sm">
            {{ section.enabled ? 'Enabled' : 'Disabled' }}
          </UBadge>
          <USwitch v-model="section.enabled" />
        </div>
      </div>
    </template>

    <div v-if="section.enabled" class="space-y-4">
      <UFormField v-for="field in knownFields" :key="field.key" :label="field.label">
        <UInput
          v-model="section.known[field.key]"
          :type="field.type ?? 'text'"
          class="w-full font-mono"
        />
      </UFormField>

      <div v-if="optionalFields.length || section.extra.length">
        <p class="text-sm text-muted mb-2">Optional fields</p>
        <ConfigOptionalFieldList
          :fields="optionalFields"
          v-model:known="section.known"
          v-model:extra="section.extra"
        />
      </div>
    </div>
    <p v-else class="text-sm text-dimmed">Disabled</p>
  </UCard>
</template>

<script setup lang="ts">
import type { PluginSection, FieldDef } from '~/composables/useConfigStore'

withDefaults(defineProps<{
  label: string
  description?: string
  icon?: string
  knownFields: FieldDef[]
  optionalFields?: FieldDef[]
}>(), {
  optionalFields: () => [],
})

const section = defineModel<PluginSection>({ required: true })
</script>
