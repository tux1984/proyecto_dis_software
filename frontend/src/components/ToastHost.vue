<script setup>
import { useToast } from '@/composables/useToast'
const { state, dismiss } = useToast()
</script>

<template>
  <div class="fixed bottom-4 right-4 z-50 flex w-80 flex-col gap-2">
    <div
      v-for="t in state.items"
      :key="t.id"
      class="rounded-md border p-3 text-sm shadow-lg"
      :class="t.type === 'error' ? 'border-red-300 bg-red-50 text-red-800' : 'border-green-300 bg-green-50 text-green-800'"
    >
      <div class="flex items-start justify-between gap-2">
        <span>{{ t.message }}</span>
        <button class="text-xs opacity-60 hover:opacity-100" @click="dismiss(t.id)">✕</button>
      </div>
      <!-- trace_id para soporte: el usuario puede reportarlo (RNF-03) -->
      <div v-if="t.traceId" class="mt-1 font-mono text-[10px] opacity-70">
        trace_id: {{ t.traceId }}
      </div>
    </div>
  </div>
</template>
