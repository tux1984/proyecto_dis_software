<script setup>
import { onMounted, reactive, ref } from 'vue'
import { api, BASE } from '@/api/client'
import { useToast } from '@/composables/useToast'

const toast = useToast()
const myEvents = ref([])
const categories = ref([])
const selected = ref(null)
const inscritos = ref([])
const dashboard = ref(null)

const form = reactive({
  title: '', description: '', modality: 'presencial', capacity: 50,
  registration_type: 'gratuita', starts_at: '', ends_at: '', category_id: '',
})
const broadcast = reactive({ subject: '', body: '', segment: 'confirmed' })

async function loadMine() {
  try {
    const { data } = await api.get('/events/mine')
    myEvents.value = data.events
  } catch (e) { toast.error(e) }
}

async function createEvent() {
  try {
    const payload = {
      ...form,
      capacity: Number(form.capacity),
      category_id: form.category_id || null,
      starts_at: new Date(form.starts_at).toISOString(),
      ends_at: new Date(form.ends_at).toISOString(),
    }
    await api.post('/events', payload)
    toast.success('Evento creado en borrador')
    Object.assign(form, { title: '', description: '' })
    loadMine()
  } catch (e) { toast.error(e) }
}

async function publish(ev) {
  try {
    await api.post(`/events/${ev.id}/publish`, { request_approval: false })
    toast.success('Evento publicado')
    loadMine()
  } catch (e) { toast.error(e) }
}
async function submitForApproval(ev) {
  try {
    await api.post(`/events/${ev.id}/publish`, { request_approval: true })
    toast.success('Enviado a aprobación institucional')
    loadMine()
  } catch (e) { toast.error(e) }
}
async function cancelEvent(ev) {
  if (!confirm(`¿Cancelar "${ev.title}"? Se notificará a los inscritos.`)) return
  try {
    await api.post(`/events/${ev.id}/cancel`, {})
    toast.success('Evento cancelado')
    loadMine()
  } catch (e) { toast.error(e) }
}

async function manage(ev) {
  selected.value = ev
  inscritos.value = []
  dashboard.value = null
  try {
    const [list, dash] = await Promise.all([
      api.get(`/enrollments/event/${ev.id}`),
      api.get(`/events/${ev.id}/dashboard`),
    ])
    inscritos.value = list.data.enrollments
    dashboard.value = dash.data
  } catch (e) { toast.error(e) }
}

async function recordAttendance(userId) {
  try {
    await api.post(`/events/${selected.value.id}/attendance`, { user_id: userId })
    toast.success('Asistencia registrada')
  } catch (e) { toast.error(e) }
}
async function sendBroadcast() {
  try {
    const { data } = await api.post(`/notifications/${selected.value.id}/broadcast`, { ...broadcast })
    toast.success(`Encolado para ${data.recipients} destinatarios`)
    broadcast.subject = ''; broadcast.body = ''
  } catch (e) { toast.error(e) }
}
async function generateCerts() {
  try {
    const { data } = await api.post(`/certificates/${selected.value.id}/batch`, { cert_type: 'asistencia' })
    toast.success(`Certificados encolados: ${data.issued}`)
  } catch (e) { toast.error(e) }
}

onMounted(async () => {
  try { categories.value = (await api.get('/categories')).data.categories } catch { /* */ }
  loadMine()
})
const statusColor = {
  borrador: 'bg-gray-100 text-gray-600', pendiente: 'bg-amber-100 text-amber-700',
  publicado: 'bg-green-100 text-green-700', cancelado: 'bg-red-100 text-red-700',
}
</script>

<template>
  <div class="grid gap-6 lg:grid-cols-2">
    <!-- Crear evento -->
    <section class="card">
      <h2 class="mb-3 text-lg font-bold text-javeriana-700">Crear evento</h2>
      <div class="space-y-2">
        <input v-model="form.title" class="input" placeholder="Título" />
        <textarea v-model="form.description" class="input" rows="2" placeholder="Descripción"></textarea>
        <div class="grid grid-cols-2 gap-2">
          <select v-model="form.modality" class="input">
            <option value="presencial">Presencial</option>
            <option value="virtual">Virtual</option>
            <option value="hibrido">Híbrido</option>
          </select>
          <select v-model="form.registration_type" class="input">
            <option value="gratuita">Gratuita</option>
            <option value="paga">Paga</option>
          </select>
          <label class="text-xs text-gray-500">Inicio<input v-model="form.starts_at" type="datetime-local" class="input" /></label>
          <label class="text-xs text-gray-500">Fin<input v-model="form.ends_at" type="datetime-local" class="input" /></label>
          <input v-model="form.capacity" type="number" min="1" class="input" placeholder="Capacidad" />
          <select v-model="form.category_id" class="input">
            <option value="">Sin categoría</option>
            <option v-for="c in categories" :key="c.id" :value="c.id">{{ c.name }}</option>
          </select>
        </div>
        <button class="btn-primary w-full" @click="createEvent">Crear (borrador)</button>
      </div>
    </section>

    <!-- Mis eventos -->
    <section class="card">
      <h2 class="mb-3 text-lg font-bold text-javeriana-700">Mis eventos</h2>
      <ul class="space-y-2">
        <li v-for="ev in myEvents" :key="ev.id" class="rounded border border-gray-200 p-3">
          <div class="flex items-center justify-between">
            <span class="text-sm font-medium">{{ ev.title }}</span>
            <span class="badge" :class="statusColor[ev.status]">{{ ev.status }}</span>
          </div>
          <div class="mt-2 flex flex-wrap gap-2">
            <button v-if="ev.status === 'borrador'" class="btn-ghost text-xs" @click="publish(ev)">Publicar</button>
            <button v-if="ev.status === 'borrador'" class="btn-ghost text-xs" @click="submitForApproval(ev)">Enviar a aprobación</button>
            <button class="btn-ghost text-xs" @click="manage(ev)">Gestionar</button>
            <button v-if="ev.status !== 'cancelado'" class="btn-ghost text-xs text-red-600" @click="cancelEvent(ev)">Cancelar</button>
          </div>
        </li>
      </ul>
    </section>

    <!-- Panel de gestión -->
    <section v-if="selected" class="card lg:col-span-2">
      <h2 class="mb-3 text-lg font-bold text-javeriana-700">Gestión: {{ selected.title }}</h2>
      <div v-if="dashboard" class="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div class="rounded bg-gray-50 p-3 text-center"><div class="text-2xl font-bold">{{ dashboard.confirmed }}</div><div class="text-xs text-gray-500">Confirmados</div></div>
        <div class="rounded bg-gray-50 p-3 text-center"><div class="text-2xl font-bold">{{ dashboard.capacity }}</div><div class="text-xs text-gray-500">Capacidad</div></div>
        <div class="rounded bg-gray-50 p-3 text-center"><div class="text-2xl font-bold">{{ (dashboard.occupancy_rate * 100).toFixed(0) }}%</div><div class="text-xs text-gray-500">Ocupación</div></div>
        <div class="rounded bg-gray-50 p-3 text-center"><div class="text-2xl font-bold">{{ dashboard.attendance }}</div><div class="text-xs text-gray-500">Asistencias</div></div>
      </div>

      <div class="grid gap-4 md:grid-cols-2">
        <div>
          <div class="mb-2 flex items-center justify-between">
            <h3 class="font-semibold">Inscritos ({{ inscritos.length }})</h3>
            <a :href="`${BASE}/enrollments/event/${selected.id}/export.csv`" class="btn-ghost text-xs">Exportar CSV</a>
          </div>
          <div class="max-h-64 overflow-y-auto rounded border border-gray-200">
            <table class="w-full text-xs">
              <thead class="bg-gray-50 text-left"><tr><th class="p-2">Nombre</th><th class="p-2">Estado</th><th class="p-2"></th></tr></thead>
              <tbody>
                <tr v-for="i in inscritos" :key="i.enrollment_id" class="border-t">
                  <td class="p-2">{{ i.full_name }}</td>
                  <td class="p-2">{{ i.status }}</td>
                  <td class="p-2"><button class="text-javeriana-600 underline" @click="recordAttendance(i.user_id)">asistió</button></td>
                </tr>
              </tbody>
            </table>
          </div>
          <button class="btn-ghost mt-2 w-full text-xs" @click="generateCerts">Generar certificados (lote)</button>
        </div>

        <div>
          <h3 class="mb-2 font-semibold">Comunicación masiva</h3>
          <input v-model="broadcast.subject" class="input mb-2" placeholder="Asunto" />
          <textarea v-model="broadcast.body" class="input mb-2" rows="3" placeholder="Mensaje"></textarea>
          <select v-model="broadcast.segment" class="input mb-2">
            <option value="confirmed">Solo confirmados</option>
            <option value="all">Todos</option>
            <option value="cancelled">Cancelados</option>
          </select>
          <button class="btn-primary w-full" @click="sendBroadcast">Enviar (asíncrono)</button>
        </div>
      </div>
    </section>
  </div>
</template>
