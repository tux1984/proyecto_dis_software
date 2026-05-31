// Store de autenticación (Pinia = Model en MVVM).
// Persiste el JWT y el usuario; expone el rol para el AuthGuard y la UI.
import { defineStore } from 'pinia'
import { api, registerTokenProvider } from '@/api/client'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    accessToken: localStorage.getItem('pgea_token') || null,
    refreshToken: localStorage.getItem('pgea_refresh') || null,
    user: JSON.parse(localStorage.getItem('pgea_user') || 'null'),
  }),
  getters: {
    isAuthenticated: (s) => !!s.accessToken,
    role: (s) => s.user?.role || null,
    fullName: (s) => s.user?.full_name || s.user?.email || '',
  },
  actions: {
    async login(idToken) {
      // SSO mock: el id_token es el correo institucional.
      const { data } = await api.post('/auth/login', { id_token: idToken }, { auth: false })
      this._persist(data)
      return data.user
    },
    logout() {
      this.accessToken = null
      this.refreshToken = null
      this.user = null
      localStorage.removeItem('pgea_token')
      localStorage.removeItem('pgea_refresh')
      localStorage.removeItem('pgea_user')
    },
    _persist(data) {
      this.accessToken = data.access_token
      this.refreshToken = data.refresh_token
      this.user = data.user
      localStorage.setItem('pgea_token', data.access_token)
      localStorage.setItem('pgea_refresh', data.refresh_token)
      localStorage.setItem('pgea_user', JSON.stringify(data.user))
    },
  },
})

// Conecta el proveedor de token del ApiClient con el store (DI sencilla).
export function wireApiToken() {
  registerTokenProvider(() => localStorage.getItem('pgea_token'))
}
