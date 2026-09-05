<template>
  <BrandScreen>
    <UCard>
      <template #header>
        <h2 class="text-lg font-semibold">Log in</h2>
      </template>
      <UForm :schema="schema" :state="state" class="space-y-4" @submit="onSubmit">
        <UFormField label="Username" name="username" required>
          <UInput v-model="state.username" class="w-full" autocomplete="username" />
        </UFormField>
        <UFormField label="Password" name="password" required>
          <UInput v-model="state.password" type="password" class="w-full" autocomplete="current-password" />
        </UFormField>
        <div class="flex justify-end">
          <UButton type="submit" :loading="pending">Log in</UButton>
        </div>
      </UForm>
    </UCard>
  </BrandScreen>
</template>

<script setup lang="ts">
import { z } from 'zod'

definePageMeta({ layout: false })

const schema = z.object({
  username: z.string().min(1, 'This field is required!'),
  password: z.string().min(1, 'This field is required!'),
})

const state = reactive({ username: '', password: '' })
const pending = ref(false)
const { login } = useAuth()
const { showError } = useToastError()
const router = useRouter()

async function onSubmit() {
  pending.value = true
  try {
    await login(state.username, state.password)
    router.push('/')
  } catch (e: any) {
    showError(e?.data?.message ?? 'Could not log in')
  } finally {
    pending.value = false
  }
}
</script>
