import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from './api.js'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') || '')
  const user = ref(null)

  const isLoggedIn = computed(() => !!token.value)
  const isSuperadmin = computed(() => user.value?.is_superadmin ?? false)
  const isAdmin = computed(() => user.value?.is_superadmin || user.value?.is_org_admin)

  async function login(username, password) {
    const res = await api.post('/auth/login', { username, password })
    token.value = res.data.access_token
    localStorage.setItem('token', token.value)
    await fetchMe()
  }

  async function fetchMe() {
    try {
      const res = await api.get('/users/me')
      user.value = res.data
    } catch {
      logout()
    }
  }

  function logout() {
    token.value = ''
    user.value = null
    localStorage.removeItem('token')
  }

  if (token.value) fetchMe()

  return { token, user, isLoggedIn, isSuperadmin, isAdmin, login, logout, fetchMe }
})
