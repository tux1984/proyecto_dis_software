<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const role = computed(() => auth.role)

function logout() {
  auth.logout()
  router.push({ name: 'login' })
}
</script>

<template>
  <header class="border-b border-gray-200 bg-javeriana-700 text-white">
    <nav class="mx-auto flex max-w-6xl flex-wrap items-center gap-4 px-4 py-3">
      <router-link to="/catalog" class="text-lg font-bold tracking-tight">🎓 PGEA</router-link>
      <router-link to="/catalog" class="text-sm hover:underline">Catálogo</router-link>
      <router-link v-if="auth.isAuthenticated" to="/me/enrollments" class="text-sm hover:underline">
        Mis inscripciones
      </router-link>
      <router-link v-if="auth.isAuthenticated" to="/me/certificates" class="text-sm hover:underline">
        Certificados
      </router-link>
      <router-link v-if="role === 'organizer' || role === 'admin'" to="/organizer" class="text-sm hover:underline">
        Organizador
      </router-link>
      <router-link v-if="role === 'admin'" to="/admin" class="text-sm hover:underline">
        Administración
      </router-link>
      <router-link to="/verify" class="text-sm hover:underline">Verificar certificado</router-link>

      <div class="ml-auto flex items-center gap-3">
        <template v-if="auth.isAuthenticated">
          <span class="hidden text-xs text-javeriana-50 sm:inline">
            {{ auth.fullName }} · <span class="font-semibold uppercase">{{ role }}</span>
          </span>
          <router-link to="/me/data" class="text-xs underline">Mis datos</router-link>
          <button class="rounded bg-white/10 px-3 py-1 text-sm hover:bg-white/20" @click="logout">
            Salir
          </button>
        </template>
        <router-link v-else to="/login" class="rounded bg-white px-3 py-1 text-sm font-medium text-javeriana-700">
          Iniciar sesión
        </router-link>
      </div>
    </nav>
  </header>
</template>
