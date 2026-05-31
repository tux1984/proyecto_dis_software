<script setup>
import { onMounted, ref } from 'vue'
import { api } from '@/api/client'
import { useToast } from '@/composables/useToast'

const toast = useToast()
const dashboard = ref(null)
const pending = ref([])
const users = ref([])
const audit = ref([])
const comment = ref({})
const roles = ['organizer', 'attendee', 'speaker', 'reviewer', 'admin']

async function loadAll() {
  try {
    const [d, p, u, a] = await Promise.all([
      api.get('/admin/dashboard'),
      api.get('/admin/events/pending'),
      api.get('/admin/users'),
      api.get('/admin/audit', { limit: 25 }),
    ])
    dashboard.value = d.data
    pending.value = p.data.events
    users.value = u.data.users
    audit.value = a.data.entries
  } catch (e) { toast.error(e) }
}
async function approve(ev) {
  const c = comment.value[ev.id] || ''
  if (c.length < 20) { toast.push('error', 'El comentario debe tener al menos 20 caracteres.'); return }
  try { await api.post(`/events/${ev.id}/approve`, { comment: c }); toast.success('Evento aprobado'); loadAll() }
  catch (e) { toast.error(e) }
}
async function reject(ev) {
  const c = comment.value[ev.id] || ''
  if (c.length < 20) { toast.push('error', 'El comentario debe tener al menos 20 caracteres.'); return }
  try { await api.post(`/events/${ev.id}/reject`, { comment: c }); toast.success('Evento rechazado'); loadAll() }
  catch (e) { toast.error(e) }
}
async function changeRole(u, role) {
  try { await api.post(`/admin/users/${u.id}/role`, { role }); toast.success(`Rol → ${role}`); loadAll() }
  catch (e) { toast.error(e) }
}
onMounted(loadAll)
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <h1 class="text-2xl font-bold text-javeriana-700">Panel institucional</h1>
      <a href="http://localhost:3000/d/pgea-red" target="_blank" class="btn-ghost text-sm">📊 Grafana (observabilidad)</a>
    </div>

    <!-- Métricas institucionales (RF-25) -->
    <section v-if="dashboard" class="grid grid-cols-2 gap-3 sm:grid-cols-4">
      <div class="card text-center"><div class="text-3xl font-bold text-javeriana-700">{{ dashboard.total_events }}</div><div class="text-xs text-gray-500">Eventos</div></div>
      <div class="card text-center"><div class="text-3xl font-bold text-javeriana-700">{{ dashboard.published_events }}</div><div class="text-xs text-gray-500">Publicados</div></div>
      <div class="card text-center"><div class="text-3xl font-bold text-javeriana-700">{{ dashboard.total_enrollments }}</div><div class="text-xs text-gray-500">Inscripciones</div></div>
      <div class="card text-center"><div class="text-3xl font-bold text-javeriana-700">{{ dashboard.confirmed_enrollments }}</div><div class="text-xs text-gray-500">Confirmadas</div></div>
    </section>

    <section v-if="dashboard" class="card">
      <h2 class="mb-2 font-semibold">Eventos por facultad</h2>
      <div class="flex flex-wrap gap-2 text-sm">
        <span v-for="(n, f) in dashboard.events_by_faculty" :key="f" class="badge bg-javeriana-50 text-javeriana-700">{{ f }}: {{ n }}</span>
      </div>
    </section>

    <!-- Aprobación institucional (RF-24, CU-07) -->
    <section class="card">
      <h2 class="mb-3 font-semibold">Eventos pendientes de aprobación</h2>
      <p v-if="!pending.length" class="text-sm text-gray-500">No hay eventos pendientes.</p>
      <div v-for="ev in pending" :key="ev.id" class="mb-3 rounded border border-amber-200 bg-amber-50 p-3">
        <div class="text-sm font-medium">{{ ev.title }}</div>
        <textarea v-model="comment[ev.id]" class="input mt-2" rows="2" placeholder="Comentario (mín. 20 caracteres)"></textarea>
        <div class="mt-2 flex gap-2">
          <button class="btn-primary text-xs" @click="approve(ev)">Aprobar</button>
          <button class="btn-ghost text-xs text-red-600" @click="reject(ev)">Rechazar</button>
        </div>
      </div>
    </section>

    <!-- Gestión de usuarios y RBAC (RF-26) -->
    <section class="card">
      <h2 class="mb-3 font-semibold">Usuarios y roles</h2>
      <div class="max-h-72 overflow-y-auto">
        <table class="w-full text-sm">
          <thead class="bg-gray-50 text-left"><tr><th class="p-2">Nombre</th><th class="p-2">Correo</th><th class="p-2">Rol</th></tr></thead>
          <tbody>
            <tr v-for="u in users" :key="u.id" class="border-t">
              <td class="p-2">{{ u.full_name }}</td>
              <td class="p-2 text-xs">{{ u.email }}</td>
              <td class="p-2">
                <select :value="u.role" class="input !py-1 text-xs" @change="changeRole(u, $event.target.value)">
                  <option v-for="r in roles" :key="r" :value="r">{{ r }}</option>
                </select>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- Auditoría inmutable (RF-29) -->
    <section class="card">
      <h2 class="mb-3 font-semibold">Auditoría reciente (append-only)</h2>
      <div class="max-h-72 overflow-y-auto">
        <table class="w-full text-xs">
          <thead class="bg-gray-50 text-left"><tr><th class="p-2">Acción</th><th class="p-2">Entidad</th><th class="p-2">Resultado</th><th class="p-2">trace_id</th></tr></thead>
          <tbody>
            <tr v-for="(e, i) in audit" :key="i" class="border-t">
              <td class="p-2">{{ e.action }}</td>
              <td class="p-2">{{ e.entity_type }}</td>
              <td class="p-2">{{ e.result }}</td>
              <td class="p-2 font-mono text-[10px] text-gray-400">{{ (e.trace_id || '').slice(0, 12) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>
