import { createRouter, createWebHistory } from 'vue-router'
import LoginView from '../views/LoginView.vue'
import OrgsView from '../views/OrgsView.vue'
import UsersView from '../views/UsersView.vue'
import RolesView from '../views/RolesView.vue'
import ResourcesView from '../views/ResourcesView.vue'
import ResolveView from '../views/ResolveView.vue'
import InteractionsView from '../views/InteractionsView.vue'

const routes = [
  { path: '/', redirect: '/login' },
  { path: '/login', component: LoginView },
  { path: '/orgs', component: OrgsView, meta: { requiresAuth: true } },
  { path: '/users', component: UsersView, meta: { requiresAuth: true } },
  { path: '/roles', component: RolesView, meta: { requiresAuth: true } },
  { path: '/resources', component: ResourcesView, meta: { requiresAuth: true } },
  { path: '/resolve', component: ResolveView, meta: { requiresAuth: true } },
  { path: '/interactions', component: InteractionsView, meta: { requiresAuth: true } },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, _from, next) => {
  const token = localStorage.getItem('token')
  if (to.meta.requiresAuth && !token) return next('/login')
  if (to.path === '/login' && token) return next('/orgs')
  next()
})

export default router
