<template>
  <div>
    <nav v-if="auth.isLoggedIn" style="background:#1e3a5f;color:#fff;padding:12px 24px;display:flex;gap:16px;align-items:center">
      <strong style="margin-right:8px">RBAC Mockup</strong>
      <router-link to="/orgs" style="color:#acd">{{ t('nav.orgs') }}</router-link>
      <router-link to="/users" style="color:#acd">{{ t('nav.users') }}</router-link>
      <router-link to="/roles" style="color:#acd">{{ t('nav.roles') }}</router-link>
      <router-link to="/resources" style="color:#acd">{{ t('nav.resources') }}</router-link>
      <router-link to="/resolve" style="color:#acd">{{ t('nav.resolve') }}</router-link>
      <router-link v-if="auth.isAdmin" to="/interactions" style="color:#acd">{{ t('nav.interactions') }}</router-link>
      <router-link to="/role-tree" style="color:#acd">{{ t('nav.roleTree') }}</router-link>
      <span style="margin-left:auto;font-size:0.85em">{{ auth.user?.username }}</span>
      <!-- Language switcher -->
      <div class="lang-switcher">
        <button :class="['lang-btn', locale === 'en' && 'lang-btn--active']" @click="setLocale('en')">EN</button>
        <button :class="['lang-btn', locale === 'uk' && 'lang-btn--active']" @click="setLocale('uk')">UK</button>
      </div>
      <button @click="auth.logout(); $router.push('/login')" style="margin-left:8px;cursor:pointer;background:#c44;border:none;color:#fff;padding:4px 10px;border-radius:4px">{{ t('nav.logout') }}</button>
    </nav>
    <div style="padding:24px;max-width:1100px;margin:0 auto">
      <router-view />
    </div>
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
import { useAuthStore } from './stores/auth.js'

const auth = useAuthStore()
const { t, locale } = useI18n()

function setLocale(lang) {
  locale.value = lang
  localStorage.setItem('locale', lang)
}
</script>

<style>
.lang-switcher { display: flex; gap: 2px; }
.lang-btn {
  padding: 2px 8px; border: 1px solid rgba(255,255,255,.4); border-radius: 3px;
  background: transparent; color: #acd; cursor: pointer; font-size: .8em;
}
.lang-btn--active { background: rgba(255,255,255,.2); color: #fff; border-color: #fff; }
</style>
