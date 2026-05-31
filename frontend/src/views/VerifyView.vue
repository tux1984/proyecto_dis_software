<script setup>
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '@/api/client'

const route = useRoute()
const code = ref(route.params.code || '')
const result = ref(null)
const error = ref('')
const loading = ref(false)

async function verify() {
  if (!code.value) return
  loading.value = true
  error.value = ''
  result.value = null
  try {
    const { data } = await api.get(`/certificates/verify/${code.value}`, undefined)
    result.value = data
  } catch (e) {
    error.value = e.message || 'Código no válido'
  } finally {
    loading.value = false
  }
}
onMounted(() => { if (code.value) verify() })
</script>

<template>
  <div class="mx-auto max-w-xl">
    <h1 class="mb-1 text-2xl font-bold text-javeriana-700">Verificación de certificado</h1>
    <p class="mb-4 text-sm text-gray-500">Verifica la autenticidad de un certificado por su código único.</p>
    <div class="card">
      <div class="flex gap-2">
        <input v-model="code" class="input" placeholder="Código de verificación" @keyup.enter="verify" />
        <button class="btn-primary" :disabled="loading" @click="verify">Verificar</button>
      </div>
      <div v-if="result" class="mt-4 rounded-md border border-green-300 bg-green-50 p-4 text-sm text-green-800">
        ✅ Certificado válido
        <dl class="mt-2 grid grid-cols-3 gap-1">
          <dt class="font-medium">Titular</dt><dd class="col-span-2">{{ result.full_name }}</dd>
          <dt class="font-medium">Evento</dt><dd class="col-span-2">{{ result.event_title }}</dd>
          <dt class="font-medium">Tipo</dt><dd class="col-span-2">{{ result.type }}</dd>
        </dl>
      </div>
      <div v-else-if="error" class="mt-4 rounded-md border border-red-300 bg-red-50 p-4 text-sm text-red-800">
        ❌ {{ error }}
      </div>
    </div>
  </div>
</template>
