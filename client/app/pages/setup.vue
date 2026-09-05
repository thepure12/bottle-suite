<template>
  <BrandScreen>
    <UCard>
      <template #header>
        <h2 class="text-lg font-semibold">Set up dashboard admin</h2>
      </template>
      <UAlert
        icon="i-lucide-shield-check"
        variant="soft"
        color="neutral"
        class="mb-4"
        description="No admin credentials are configured yet. Choose a username and password to secure the dashboard."
      />
      <UForm :schema="schema" :state="state" class="space-y-4" @submit="onSubmit">
        <UFormField label="Username" name="username" required>
          <UInput v-model="state.username" class="w-full" autocomplete="username" />
        </UFormField>
        <UFormField label="Password" name="password" required>
          <UInput v-model="state.password" type="password" class="w-full" autocomplete="new-password" />
        </UFormField>
        <UFormField label="Confirm password" name="confirmPassword" required>
          <UInput v-model="state.confirmPassword" type="password" class="w-full" autocomplete="new-password" />
        </UFormField>
        <div class="flex justify-end">
          <UButton type="submit" :loading="pending">Create admin account</UButton>
        </div>
      </UForm>
    </UCard>
  </BrandScreen>
</template>

<script setup lang="ts">
import { z } from 'zod'

definePageMeta({ layout: false })

const schema = z
  .object({
    username: z.string().min(1, 'This field is required!'),
    password: z.string().min(8, 'Password must be at least 8 characters.'),
    confirmPassword: z.string().min(1, 'This field is required!'),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: 'Passwords do not match.',
    path: ['confirmPassword'],
  })

const state = reactive({ username: '', password: '', confirmPassword: '' })
const pending = ref(false)
const { submitSetup } = useSetup()
const { showError, showSuccess } = useToastError()
const router = useRouter()

async function onSubmit() {
  pending.value = true
  try {
    await submitSetup(state.username, state.password)
    showSuccess('Admin account created. You can now log in.')
    router.push('/login')
  } catch (e: any) {
    showError(e?.data?.message ?? 'Could not complete setup')
  } finally {
    pending.value = false
  }
}
</script>
