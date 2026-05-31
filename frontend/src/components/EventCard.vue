<script setup>
defineProps({ event: { type: Object, required: true } })

function fmtDate(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleString('es-CO', {
    day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}
const modalityColor = {
  presencial: 'bg-blue-100 text-blue-700',
  virtual: 'bg-purple-100 text-purple-700',
  hibrido: 'bg-amber-100 text-amber-700',
}
</script>

<template>
  <router-link :to="`/events/${event.id}`" class="card block transition hover:shadow-md">
    <div class="mb-2 flex items-center gap-2">
      <span class="badge" :class="modalityColor[event.modality] || 'bg-gray-100 text-gray-600'">
        {{ event.modality }}
      </span>
      <span class="badge bg-gray-100 text-gray-600">{{ event.registration_type }}</span>
    </div>
    <h3 class="line-clamp-2 font-semibold text-javeriana-700">{{ event.title }}</h3>
    <p class="mt-1 line-clamp-2 text-sm text-gray-600">{{ event.description }}</p>
    <div class="mt-3 flex items-center justify-between text-xs text-gray-500">
      <span>📅 {{ fmtDate(event.starts_at) }}</span>
      <span>👥 {{ event.capacity }} cupos</span>
    </div>
  </router-link>
</template>
