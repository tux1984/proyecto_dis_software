// Vue Router + AuthGuard (SAD §6.1.4).
// La seguridad definitiva es del backend (RBAC); el AuthGuard mejora la UX
// ocultando rutas no autorizadas y exigiendo sesión.
import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes = [
  { path: '/', redirect: '/catalog' },
  { path: '/login', name: 'login', component: () => import('@/views/LoginView.vue') },
  { path: '/catalog', name: 'catalog', component: () => import('@/views/CatalogView.vue') },
  { path: '/events/:id', name: 'event', component: () => import('@/views/EventDetailView.vue') },
  { path: '/verify/:code?', name: 'verify', component: () => import('@/views/VerifyView.vue') },
  { path: '/speakers/respond', name: 'speaker-respond', component: () => import('@/views/SpeakerRespondView.vue') },
  {
    path: '/pay', name: 'pay',
    component: () => import('@/views/PaymentMockView.vue'), meta: { auth: true },
  },
  {
    path: '/me/enrollments', name: 'my-enrollments',
    component: () => import('@/views/MyEnrollmentsView.vue'), meta: { auth: true },
  },
  {
    path: '/me/certificates', name: 'my-certificates',
    component: () => import('@/views/CertificatesView.vue'), meta: { auth: true },
  },
  {
    path: '/me/data', name: 'my-data',
    component: () => import('@/views/MyDataView.vue'), meta: { auth: true },
  },
  {
    path: '/organizer', name: 'organizer',
    component: () => import('@/views/OrganizerPortal.vue'), meta: { auth: true, roles: ['organizer', 'admin'] },
  },
  {
    path: '/admin', name: 'admin',
    component: () => import('@/views/AdminView.vue'), meta: { auth: true, roles: ['admin'] },
  },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.meta.auth && !auth.isAuthenticated) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.meta.roles && !to.meta.roles.includes(auth.role)) {
    return { name: 'catalog' } // sin rol suficiente: vuelve al catálogo
  }
  return true
})

export default router
