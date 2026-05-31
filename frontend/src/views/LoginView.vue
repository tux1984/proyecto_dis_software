<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const toast = useToast()

const email = ref('')
const consent = ref(false)
const loading = ref(false)

// Cuentas sembradas (SSO mock): el id_token es el correo institucional.
const quick = [
  { label: 'Administrador', email: 'admin@javeriana.edu.co' },
  { label: 'Organizador', email: 'organizador1@javeriana.edu.co' },
  { label: 'Asistente', email: 'asistente1@javeriana.edu.co' },
  { label: 'Ponente', email: 'ponente1@javeriana.edu.co' },
]

async function doLogin(value) {
  if (!consent.value) {
    toast.push('error', 'Debes aceptar la política de tratamiento de datos (Ley 1581).')
    return
  }
  loading.value = true
  try {
    await auth.login(value)
    toast.success('Sesión iniciada')
    router.push(route.query.redirect || '/catalog')
  } catch (e) {
    toast.error(e)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="mx-auto max-w-md">
    <div class="card">
      <h1 class="text-xl font-bold text-javeriana-700">Iniciar sesión</h1>
      <p class="mt-1 text-sm text-gray-500">
        Autenticación SSO delegada (OAuth 2.0 / OIDC) — adaptador mock en el POC.
      </p>

      <div class="mt-5">
        <label class="label">Correo institucional</label>
        <input v-model="email" class="input" placeholder="usuario@javeriana.edu.co" @keyup.enter="doLogin(email)" />
      </div>

      <label class="mt-3 flex items-start gap-2 text-xs text-gray-600">
        <input v-model="consent" type="checkbox" class="mt-0.5" />
        <span>
          Acepto la <a href="#" class="text-javeriana-600 underline">política de tratamiento de datos personales</a>
          conforme a la Ley 1581 de 2012. El consentimiento se registra con marca de tiempo.
        </span>
      </label>

      <button class="btn-primary mt-4 w-full" :disabled="loading || !email" @click="doLogin(email)">
        Ingresar
      </button>

      <div class="mt-6">
        <p class="mb-2 text-xs font-medium uppercase tracking-wide text-gray-400">Acceso rápido (demo)</p>
        <div class="grid grid-cols-2 gap-2">
          <button v-for="q in quick" :key="q.email" class="btn-ghost text-xs" :disabled="loading"
                  @click="email = q.email; doLogin(q.email)">
            {{ q.label }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
