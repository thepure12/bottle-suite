// Replaces components/Toast.vue and the old this.$root.vtoast/$nuxt.vtoast
// imperative-ref plumbing. Nuxt UI's toasts are dismissible by default,
// which also fixes the old Toast.vue's "dismassable" typo (it never
// actually worked) for free.
export function useToastError() {
  const toast = useToast()

  function showError(message: string) {
    toast.add({
      title: 'Error',
      description: message,
      color: 'error',
      icon: 'i-lucide-octagon-x',
    })
  }

  function showSuccess(message: string) {
    toast.add({
      title: 'Success',
      description: message,
      color: 'success',
      icon: 'i-lucide-check',
    })
  }

  return { showError, showSuccess }
}
