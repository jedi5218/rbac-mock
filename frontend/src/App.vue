<template>
  <div>
    <nav v-if="auth.isLoggedIn" style="background:#1e3a5f;color:#fff;padding:12px 24px;display:flex;gap:16px;align-items:center">
      <strong style="margin-right:8px">RBAC Mockup</strong>
      <router-link to="/orgs" style="color:#acd">Orgs</router-link>
      <router-link to="/users" style="color:#acd">Users</router-link>
      <router-link to="/roles" style="color:#acd">Roles</router-link>
      <router-link to="/resources" style="color:#acd">Resources</router-link>
      <router-link to="/resolve" style="color:#acd">Resolve</router-link>
      <span style="margin-left:auto;font-size:0.85em">{{ auth.user?.username }}</span>
      <button @click="auth.logout(); $router.push('/login')" style="margin-left:8px;cursor:pointer;background:#c44;border:none;color:#fff;padding:4px 10px;border-radius:4px">Logout</button>
    </nav>
    <div style="padding:24px;max-width:1100px;margin:0 auto">
      <router-view />
    </div>
  </div>
</template>

<script setup>
import { useAuthStore } from './stores/auth.js'
const auth = useAuthStore()
</script>
