<script setup>
import AppNav from '@/components/AppNav.vue'
import ToastHost from '@/components/ToastHost.vue'
</script>

<template>
  <div class="min-h-screen bg-gray-50 text-gray-900">
    <AppNav />
    <main class="mx-auto max-w-6xl px-4 py-6">
      <router-view v-slot="{ Component }">
        <component :is="Component" />
      </router-view>
    </main>
    <ToastHost />
    <footer class="mx-auto max-w-6xl px-4 py-8 text-center text-xs text-gray-400">
      PGEA — Plataforma de Gestión de Eventos Académicos · Pontificia Universidad Javeriana · POC
    </footer>
  </div>
</template>
