<script setup>
// Pasarela de pago SIMULADA (mock, RF-04 / ADR-03). En el POC no hay proveedor
// real: esta vista representa el redireccionamiento a la pasarela. Al confirmar,
// llama al webhook público que confirma la inscripción (idempotente, RN-06).
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '@/api/client'
import { useToast } from '@/composables/useToast'

const route = useRoute()
const router = useRouter()
const toast = useToast()

const enrollmentId = route.query.enrollment_id
const paymentRef = route.query.payment_ref || `mock_${Date.now()}`
const processing = ref(false)

async function pay(status) {
  if (!enrollmentId) { toast.push('error', 'Falta la referencia de inscripción'); return }
  processing.value = true
  try {
    // El webhook de la pasarela es público; idempotency_key = referencia de pago.
    const { data } = await api.post('/enrollments/webhook', {
      enrollment_id: enrollmentId,
      status,
      idempotency_key: paymentRef,
    }, { auth: false })
    if (data.status === 'confirmada') {
      toast.success('Pago aprobado. Inscripción confirmada ✅')
    } else if (data.status === 'duplicate') {
      toast.success('El pago ya había sido procesado.')
    } else {
      toast.push('error', 'Pago rechazado: se liberó el cupo.')
    }
    setTimeout(() => router.push('/me/enrollments'), 1200)
  } catch (e) {
    toast.error(e)
  } finally {
    processing.value = false
  }
}
</script>

<template>
  <div class="mx-auto max-w-md">
    <div class="card">
      <div class="mb-1 text-xs font-medium uppercase tracking-wide text-amber-600">
        Pasarela de pago · simulada (mock)
      </div>
      <h1 class="text-xl font-bold text-javeriana-700">Confirmar pago</h1>
      <p class="mt-2 text-sm text-gray-600">
        Este es el adaptador <strong>mock</strong> de la pasarela (PSE/tarjetas). En producción se sustituye
        por el proveedor real sin tocar la lógica de negocio (ADR-03). Simula la decisión del usuario:
      </p>
      <dl class="mt-3 rounded bg-gray-50 p-3 text-xs text-gray-600">
        <div><dt class="inline font-medium">Inscripción:</dt> <dd class="inline font-mono">{{ enrollmentId }}</dd></div>
        <div><dt class="inline font-medium">Referencia:</dt> <dd class="inline font-mono">{{ paymentRef }}</dd></div>
      </dl>
      <div class="mt-4 flex gap-2">
        <button class="btn-primary flex-1" :disabled="processing" @click="pay('confirmed')">
          Pagar (aprobar)
        </button>
        <button class="btn-ghost flex-1" :disabled="processing" @click="pay('rejected')">
          Rechazar
        </button>
      </div>
      <p class="mt-3 text-xs text-gray-400">
        Al aprobar, la pasarela notifica al sistema vía webhook idempotente y la inscripción pasa a
        <code>confirmada</code>. Si no se confirma en 15 min, el cupo se libera (RN-06).
      </p>
    </div>
  </div>
</template>
