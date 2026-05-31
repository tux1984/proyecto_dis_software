<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, BASE } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const toast = useToast()

const event = ref(null)
const material = ref(null)
const speakers = ref([])
const loading = ref(true)
const registering = ref(false)

const id = route.params.id

function fmt(iso) {
  return iso ? new Date(iso).toLocaleString('es-CO') : ''
}

async function load() {
  loading.value = true
  try {
    const { data } = await api.get(`/events/${id}`)
    event.value = data
    const sp = await api.get(`/events/${id}/speakers`)
    speakers.value = sp.data.speakers
    if (auth.isAuthenticated) {
      try {
        const m = await api.get(`/events/${id}/material`)
        material.value = m.data
      } catch { /* sin acceso */ }
    }
  } catch (e) {
    toast.error(e)
  } finally {
    loading.value = false
  }
}

async function register() {
  registering.value = true
  try {
    const { data } = await api.post(`/enrollments/${id}/register`, {})
    if (data.status === 'pendiente_pago') {
      toast.success('Reserva creada. Redirigiendo a la pasarela (simulada)…')
      router.push({
        name: 'pay',
        query: { enrollment_id: data.enrollment_id, payment_ref: data.payment_reference },
      })
    } else {
      toast.success('Inscripción confirmada')
      load()
    }
  } catch (e) {
    toast.error(e)
  } finally {
    registering.value = false
  }
}

const isPaid = computed(() => event.value?.registration_type === 'paga')

onMounted(load)
</script>

<template>
  <div v-if="loading">Cargando…</div>
  <div v-else-if="event" class="grid gap-6 lg:grid-cols-3">
    <div class="lg:col-span-2">
      <span class="badge bg-gray-100 text-gray-600">{{ event.modality }}</span>
      <span class="badge ml-1" :class="event.status === 'publicado' ? 'bg-green-100 text-green-700' : 'bg-amber-100 text-amber-700'">
        {{ event.status }}
      </span>
      <h1 class="mt-2 text-2xl font-bold text-javeriana-700">{{ event.title }}</h1>
      <p class="mt-2 text-gray-700">{{ event.description }}</p>

      <div class="mt-4 grid grid-cols-2 gap-3 text-sm text-gray-600">
        <div>📅 Inicio: {{ fmt(event.starts_at) }}</div>
        <div>🏁 Fin: {{ fmt(event.ends_at) }}</div>
        <div v-if="event.location">📍 {{ event.location }}</div>
        <div>👥 Cupos: {{ event.capacity }}</div>
      </div>

      <div v-if="event.sessions?.length" class="mt-6">
        <h2 class="mb-2 font-semibold">Agenda</h2>
        <ul class="space-y-2">
          <li v-for="s in event.sessions" :key="s.id" class="card !p-3 text-sm">
            <span class="font-medium">{{ s.title }}</span>
            <span v-if="s.track" class="badge ml-2 bg-blue-100 text-blue-700">{{ s.track }}</span>
            <div class="text-xs text-gray-500">{{ fmt(s.starts_at) }} – {{ fmt(s.ends_at) }}</div>
          </li>
        </ul>
      </div>

      <div v-if="speakers.length" class="mt-6">
        <h2 class="mb-2 font-semibold">Ponentes</h2>
        <ul class="text-sm text-gray-700">
          <li v-for="(sp, i) in speakers" :key="i">🎤 {{ sp.email }} <span v-if="sp.bio">— {{ sp.bio }}</span></li>
        </ul>
      </div>

      <div v-if="material?.access === 'full'" class="mt-6 card bg-green-50">
        <h2 class="mb-1 font-semibold text-green-800">Material del evento (acceso confirmado)</h2>
        <p v-if="material.video_link" class="text-sm">🎥 Enlace: <a :href="material.video_link" class="text-javeriana-600 underline">{{ material.video_link }}</a></p>
        <p v-else class="text-sm text-gray-600">El material se publicará próximamente.</p>
      </div>
    </div>

    <aside class="space-y-3">
      <div class="card">
        <p class="text-sm text-gray-600">
          {{ isPaid ? 'Evento de pago (pasarela mock).' : 'Evento gratuito.' }}
        </p>
        <button class="btn-primary mt-3 w-full" :disabled="registering || event.status !== 'publicado'" @click="register">
          {{ isPaid ? 'Inscribirse y pagar' : 'Inscribirme' }}
        </button>
        <a :href="`${BASE}/events/${id}/calendar.ics`" class="btn-ghost mt-2 w-full">📆 Agregar a mi calendario (.ics)</a>
        <p v-if="!auth.isAuthenticated" class="mt-2 text-xs text-gray-500">
          Inicia sesión para inscribirte.
        </p>
      </div>
    </aside>
  </div>
</template>
