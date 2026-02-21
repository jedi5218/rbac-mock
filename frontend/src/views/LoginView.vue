<template>
  <div style="max-width:360px;margin:80px auto;background:#fff;padding:32px;border-radius:8px;box-shadow:0 2px 12px rgba(0,0,0,.15)">
    <h2 style="margin-bottom:24px;text-align:center">{{ t('login.title') }}</h2>
    <form @submit.prevent="submit">
      <div style="margin-bottom:16px">
        <label>{{ t('login.username') }}</label>
        <input v-model="form.username" style="display:block;width:100%;padding:8px;margin-top:4px;border:1px solid #ccc;border-radius:4px" />
      </div>
      <div style="margin-bottom:20px">
        <label>{{ t('login.password') }}</label>
        <input type="password" v-model="form.password" style="display:block;width:100%;padding:8px;margin-top:4px;border:1px solid #ccc;border-radius:4px" />
      </div>
      <button type="submit" :disabled="loading" style="width:100%;padding:10px;background:#1e3a5f;color:#fff;border:none;border-radius:4px;cursor:pointer;font-size:1em">
        {{ loading ? t('login.submitting') : t('login.submit') }}
      </button>
      <p v-if="error" style="color:red;margin-top:12px;text-align:center">{{ error }}</p>
    </form>
    <p style="margin-top:20px;text-align:center;font-size:0.85em;color:#888">{{ t('login.hint') }}</p>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '../stores/auth.js'

const { t } = useI18n()
const auth = useAuthStore()
const router = useRouter()
const form = ref({ username: '', password: '' })
const loading = ref(false)
const error = ref('')

async function submit() {
  error.value = ''
  loading.value = true
  try {
    await auth.login(form.value.username, form.value.password)
    router.push('/orgs')
  } catch (e) {
    error.value = e.response?.data?.detail || 'Login failed'
  } finally {
    loading.value = false
  }
}
</script>
