// ApiClient — envoltura HTTP (SAD §6.1.4).
// Agrega Authorization: Bearer y captura X-Trace-Id de cada respuesta para
// correlación de soporte (RNF-03). Centraliza el manejo de errores con trace_id.

const BASE = import.meta.env.VITE_API_BASE_URL || '/api'

export class ApiError extends Error {
  constructor(message, { status, code, traceId } = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.traceId = traceId
  }
}

let getToken = () => null
export function registerTokenProvider(fn) {
  getToken = fn
}

async function request(method, path, { body, params, auth = true } = {}) {
  const url = new URL(BASE + path, window.location.origin)
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') url.searchParams.set(k, v)
    })
  }
  const headers = { 'Content-Type': 'application/json' }
  const token = auth ? getToken() : null
  if (token) headers['Authorization'] = `Bearer ${token}`

  const resp = await fetch(url.pathname + url.search, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  const traceId = resp.headers.get('X-Trace-Id')

  // 204 / respuestas sin cuerpo
  const text = await resp.text()
  const data = text ? safeJson(text) : null

  if (!resp.ok) {
    const detail = (data && (data.detail || data.error)) || resp.statusText
    throw new ApiError(detail, {
      status: resp.status,
      code: data && data.error,
      traceId: (data && data.trace_id) || traceId,
    })
  }
  return { data, traceId }
}

function safeJson(text) {
  try {
    return JSON.parse(text)
  } catch {
    return text
  }
}

export const api = {
  get: (path, params) => request('GET', path, { params }),
  post: (path, body, opts) => request('POST', path, { body, ...opts }),
  patch: (path, body) => request('PATCH', path, { body }),
  del: (path) => request('DELETE', path, {}),
  // Para descargas (CSV / ICS / PDF) devolvemos el texto crudo.
  raw: async (path) => {
    const token = getToken()
    const resp = await fetch(BASE + path, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    if (!resp.ok) throw new ApiError('Error al descargar', { status: resp.status })
    return resp.text()
  },
}

export { BASE }
