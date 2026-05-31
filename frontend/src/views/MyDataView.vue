<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'

const toast = useToast()
const router = useRouter()
const auth = useAuthStore()
const data = ref(null)

async function load() {
  try {
    const r = await api.get('/me/data')
    data.value = r.data
  } catch (e) { toast.error(e) }
}
async function requestDeletion() {
  if (!confirm('¿Solicitar la supresión (anonimización) de tus datos personales?')) return
  try {
    await api.del('/me/data')
    toast.success('Datos anonimizados. Cerrando sesión…')
    auth.logout()
    router.push('/login')
  } catch (e) { toast.error(e) }
}
onMounted(load)
</script>

<template>
  <div class="mx-auto max-w-2xl">
    <h1 class="mb-1 text-2xl font-bold text-javeriana-700">Mis datos personales</h1>
    <p class="mb-4 text-sm text-gray-500">
      Conforme a la Ley 1581 de 2012: consulta y supresión de tus datos. Cada acceso queda auditado.
    </p>
    <div v-if="data" class="card">
      <dl class="grid grid-cols-3 gap-2 text-sm">
        <dt class="font-medium text-gray-500">Nombre</dt><dd class="col-span-2">{{ data.full_name }}</dd>
        <dt class="font-medium text-gray-500">Correo</dt><dd class="col-span-2">{{ data.email }}</dd>
        <dt class="font-medium text-gray-500">Rol</dt><dd class="col-span-2">{{ data.role }}</dd>
        <dt class="font-medium text-gray-500">Consentimiento</dt><dd class="col-span-2">{{ data.consent_accepted_at || '—' }}</dd>
        <dt class="font-medium text-gray-500">Inscripciones</dt><dd class="col-span-2">{{ data.enrollments.length }}</dd>
      </dl>
      <button class="btn mt-4 border border-red-300 bg-red-50 text-red-700 hover:bg-red-100" @click="requestDeletion">
        Solicitar supresión de mis datos
      </button>
    </div>
  </div>
</template>
