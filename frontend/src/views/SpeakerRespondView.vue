<script setup>
import { ref } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '@/api/client'
import { useToast } from '@/composables/useToast'

const route = useRoute()
const toast = useToast()
const token = ref(route.query.token || '')
const bio = ref('')
const material = ref('')
const done = ref(null)

async function respond(accept) {
  if (!token.value) { toast.push('error', 'Falta el token de invitación'); return }
  try {
    const { data } = await api.post(
      `/speakers/respond?token=${encodeURIComponent(token.value)}`,
      { accept, bio: bio.value || null, material_url: material.value || null },
      { auth: false },
    )
    done.value = data.status
    toast.success(`Participación ${data.status}`)
  } catch (e) { toast.error(e) }
}
</script>

<template>
  <div class="mx-auto max-w-lg">
    <h1 class="mb-1 text-2xl font-bold text-javeriana-700">Invitación como ponente</h1>
    <p class="mb-4 text-sm text-gray-500">Confirma o declina tu participación (token de un solo uso).</p>
    <div v-if="!done" class="card space-y-3">
      <div>
        <label class="label">Token</label>
        <input v-model="token" class="input" placeholder="Token de invitación" />
      </div>
      <div>
        <label class="label">Biografía (opcional)</label>
        <textarea v-model="bio" class="input" rows="3"></textarea>
      </div>
      <div>
        <label class="label">URL del material (opcional)</label>
        <input v-model="material" class="input" placeholder="https://…" />
      </div>
      <div class="flex gap-2">
        <button class="btn-primary flex-1" @click="respond(true)">Aceptar participación</button>
        <button class="btn-ghost flex-1" @click="respond(false)">Declinar</button>
      </div>
    </div>
    <div v-else class="card text-center text-green-700">Participación {{ done }} ✅</div>
  </div>
</template>
