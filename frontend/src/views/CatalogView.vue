<script setup>
import { onMounted, reactive, ref } from 'vue'
import { api } from '@/api/client'
import { useToast } from '@/composables/useToast'
import EventCard from '@/components/EventCard.vue'

const toast = useToast()
const events = ref([])
const categories = ref([])
const loading = ref(false)
const filters = reactive({ q: '', semantic: false, modality: '', category_id: '', sort: 'date_asc' })

async function load() {
  loading.value = true
  try {
    const path = filters.semantic ? '/search' : '/events'
    const params = {
      q: filters.q || undefined,
      modality: filters.modality || undefined,
      category_id: filters.category_id || undefined,
      sort: filters.sort,
      semantic: filters.semantic ? 'true' : undefined,
      limit: 50,
    }
    const { data } = await api.get(path, params)
    events.value = data.results
  } catch (e) {
    toast.error(e)
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  try {
    const { data } = await api.get('/categories')
    categories.value = data.categories
  } catch { /* opcional */ }
  load()
})
</script>

<template>
  <div>
    <div class="mb-5 flex flex-col gap-2">
      <h1 class="text-2xl font-bold text-javeriana-700">Catálogo de eventos</h1>
      <p class="text-sm text-gray-500">Descubre, filtra y busca eventos académicos.</p>
    </div>

    <div class="card mb-5">
      <div class="flex flex-col gap-3 md:flex-row md:items-end">
        <div class="flex-1">
          <label class="label">Búsqueda</label>
          <input v-model="filters.q" class="input" placeholder="Ej: inteligencia artificial" @keyup.enter="load" />
        </div>
        <div>
          <label class="label">Modalidad</label>
          <select v-model="filters.modality" class="input">
            <option value="">Todas</option>
            <option value="presencial">Presencial</option>
            <option value="virtual">Virtual</option>
            <option value="hibrido">Híbrido</option>
          </select>
        </div>
        <div>
          <label class="label">Categoría</label>
          <select v-model="filters.category_id" class="input">
            <option value="">Todas</option>
            <option v-for="c in categories" :key="c.id" :value="c.id">{{ c.name }}</option>
          </select>
        </div>
        <div>
          <label class="label">Orden</label>
          <select v-model="filters.sort" class="input">
            <option value="date_asc">Fecha ↑</option>
            <option value="date_desc">Fecha ↓</option>
            <option value="title">Título A-Z</option>
          </select>
        </div>
        <button class="btn-primary" @click="load">Buscar</button>
      </div>
      <label class="mt-3 flex items-center gap-2 text-sm text-gray-600">
        <input v-model="filters.semantic" type="checkbox" @change="load" />
        Búsqueda semántica (pgvector · embeddings) — encuentra eventos relacionados conceptualmente
      </label>
    </div>

    <p v-if="loading" class="text-sm text-gray-500">Cargando…</p>
    <p v-else-if="!events.length" class="text-sm text-gray-500">No se encontraron eventos.</p>
    <div v-else class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <EventCard v-for="e in events" :key="e.id" :event="e" />
    </div>
  </div>
</template>
