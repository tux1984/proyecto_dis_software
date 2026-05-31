<script setup>
import { onMounted, ref } from 'vue'
import { api, BASE } from '@/api/client'
import { useToast } from '@/composables/useToast'

const toast = useToast()
const items = ref([])

async function load() {
  try {
    const { data } = await api.get('/certificates/mine')
    items.value = data.certificates
  } catch (e) { toast.error(e) }
}
onMounted(load)
</script>

<template>
  <div>
    <h1 class="mb-4 text-2xl font-bold text-javeriana-700">Mis certificados</h1>
    <p v-if="!items.length" class="text-sm text-gray-500">
      No tienes certificados. Se emiten tras registrarse la asistencia a un evento.
    </p>
    <ul class="space-y-2">
      <li v-for="c in items" :key="c.id" class="card flex items-center justify-between !py-3">
        <div class="text-sm">
          <span class="font-medium">{{ c.event_title }}</span>
          <span class="badge ml-2 bg-blue-100 text-blue-700">{{ c.type }}</span>
          <div class="font-mono text-xs text-gray-400">código: {{ c.verification_code }}</div>
        </div>
        <a v-if="c.pdf_url" :href="`${BASE}${c.pdf_url}`" target="_blank" class="btn-ghost text-xs">Descargar PDF</a>
        <span v-else class="text-xs text-amber-600">Generando…</span>
      </li>
    </ul>
  </div>
</template>
