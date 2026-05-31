<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '@/api/client'
import { useToast } from '@/composables/useToast'

const toast = useToast()
const router = useRouter()
const items = ref([])

async function load() {
  try {
    const { data } = await api.get('/enrollments/mine')
    items.value = data.enrollments
  } catch (e) { toast.error(e) }
}
async function cancel(id) {
  try {
    await api.post(`/enrollments/${id}/cancel`, {})
    toast.success('Inscripción cancelada')
    load()
  } catch (e) { toast.error(e) }
}
async function requestCertificate(eventId) {
  try {
    await api.post(`/certificates/${eventId}/request`, { cert_type: 'asistencia' })
    toast.success('Certificado solicitado. Aparecerá en "Certificados" en unos segundos.')
    setTimeout(() => router.push('/me/certificates'), 1200)
  } catch (e) { toast.error(e) }   // 403 si no hay asistencia registrada (RN-05)
}
function fmt(iso) {
  return iso
    ? new Date(iso).toLocaleString('es-CO', { day: '2-digit', month: 'short', year: 'numeric' })
    : ''
}
const color = {
  confirmada: 'bg-green-100 text-green-700', pendiente_pago: 'bg-amber-100 text-amber-700',
  cancelada: 'bg-gray-100 text-gray-600', expirada: 'bg-red-100 text-red-700',
}
onMounted(load)
</script>

<template>
  <div>
    <h1 class="mb-4 text-2xl font-bold text-javeriana-700">Mis inscripciones</h1>
    <p v-if="!items.length" class="text-sm text-gray-500">Aún no tienes inscripciones.</p>
    <ul class="space-y-2">
      <li v-for="e in items" :key="e.id" class="card flex flex-wrap items-center justify-between gap-3 !py-3">
        <div class="min-w-0">
          <router-link :to="`/events/${e.event_id}`" class="font-medium text-javeriana-600 hover:underline">
            {{ e.event_title }}
          </router-link>
          <span class="badge ml-2" :class="color[e.status]">{{ e.status }}</span>
          <div class="text-xs text-gray-500">📅 {{ fmt(e.event_starts_at) }} · {{ e.modality }}</div>
        </div>
        <div class="flex items-center gap-2">
          <button v-if="e.status === 'confirmada'" class="btn-ghost text-xs"
                  @click="requestCertificate(e.event_id)">Solicitar certificado</button>
          <button v-if="e.status === 'confirmada' || e.status === 'pendiente_pago'"
                  class="btn-ghost text-xs text-red-600" @click="cancel(e.id)">Cancelar</button>
        </div>
      </li>
    </ul>
    <p class="mt-4 text-xs text-gray-400">
      El certificado se emite solo si el organizador registró tu asistencia (regla RN-05).
    </p>
  </div>
</template>
