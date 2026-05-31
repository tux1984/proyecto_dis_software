// useToast — ViewModel de feedback (errores con trace_id para soporte).
import { reactive } from 'vue'

const state = reactive({ items: [] })
let seq = 0

export function useToast() {
  function push(type, message, traceId) {
    const id = ++seq
    state.items.push({ id, type, message, traceId })
    setTimeout(() => dismiss(id), type === 'error' ? 9000 : 4000)
  }
  function dismiss(id) {
    const i = state.items.findIndex((t) => t.id === id)
    if (i >= 0) state.items.splice(i, 1)
  }
  function success(msg) { push('success', msg) }
  function error(err) {
    const msg = err?.message || 'Ocurrió un error'
    push('error', msg, err?.traceId)
  }
  return { state, push, dismiss, success, error }
}
