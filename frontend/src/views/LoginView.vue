<template>
  <div style="max-width:480px;margin:60px auto">
    <!-- Language switcher -->
    <div style="display:flex;justify-content:flex-end;margin-bottom:12px">
      <div class="lang-switcher">
        <button :class="['lang-btn', locale === 'en' && 'lang-btn--active']" @click="setLocale('en')">EN</button>
        <button :class="['lang-btn', locale === 'uk' && 'lang-btn--active']" @click="setLocale('uk')">UK</button>
      </div>
    </div>

    <!-- Login form -->
    <div style="background:#fff;padding:32px;border-radius:8px;box-shadow:0 2px 12px rgba(0,0,0,.15)">
      <h2 style="margin-bottom:24px;text-align:center">{{ t('login.title') }}</h2>
      <form @submit.prevent="submit">
        <div style="margin-bottom:16px">
          <label>{{ t('login.username') }}</label>
          <input v-model="form.username" style="display:block;width:100%;padding:8px;margin-top:4px;border:1px solid #ccc;border-radius:4px;box-sizing:border-box" />
        </div>
        <div style="margin-bottom:20px">
          <label>{{ t('login.password') }}</label>
          <input type="password" v-model="form.password" style="display:block;width:100%;padding:8px;margin-top:4px;border:1px solid #ccc;border-radius:4px;box-sizing:border-box" />
        </div>
        <button type="submit" :disabled="loading" style="width:100%;padding:10px;background:#1e3a5f;color:#fff;border:none;border-radius:4px;cursor:pointer;font-size:1em">
          {{ loading ? t('login.submitting') : t('login.submit') }}
        </button>
        <p v-if="error" style="color:red;margin-top:12px;text-align:center">{{ error }}</p>
      </form>
      <p style="margin-top:16px;text-align:center;font-size:0.85em;color:#888">
        {{ t('login.hint') }}
        &nbsp;·&nbsp;
        <router-link to="/wiki/index" style="color:#1e3a5f">{{ t('wiki.title') }}</router-link>
      </p>
    </div>

    <!-- Quick login user list -->
    <div v-if="demoUsers.length" style="background:#fff;padding:20px 24px;border-radius:8px;box-shadow:0 1px 4px rgba(0,0,0,.1);margin-top:16px">
      <div style="font-size:.85em;font-weight:600;color:#555;text-transform:uppercase;letter-spacing:.04em;margin-bottom:10px">{{ t('login.quickLogin') }}</div>
      <table style="width:100%;border-collapse:collapse">
        <thead>
          <tr>
            <th style="text-align:left;padding:4px 8px;font-size:.8em;color:#888;border-bottom:1px solid #eee">{{ t('login.username') }}</th>
            <th style="text-align:left;padding:4px 8px;font-size:.8em;color:#888;border-bottom:1px solid #eee">{{ t('common.org') }}</th>
            <th style="text-align:left;padding:4px 8px;font-size:.8em;color:#888;border-bottom:1px solid #eee">{{ t('login.role') }}</th>
            <th style="padding:4px 8px;border-bottom:1px solid #eee"></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="u in demoUsers" :key="u.username" style="border-bottom:1px solid #f5f5f5">
            <td style="padding:6px 8px;font-size:.9em;font-weight:500">{{ u.username }}</td>
            <td style="padding:6px 8px;font-size:.85em;color:#555">{{ u.org_name }}</td>
            <td style="padding:6px 8px">
              <span v-if="u.is_superadmin" style="padding:1px 6px;border-radius:3px;font-size:.75em;background:#1e3a5f;color:#fff">superadmin</span>
              <span v-else-if="u.is_org_admin" style="padding:1px 6px;border-radius:3px;font-size:.75em;background:#5a8ab5;color:#fff">org-admin</span>
              <span v-else style="padding:1px 6px;border-radius:3px;font-size:.75em;background:#e9ecef;color:#555">user</span>
            </td>
            <td style="padding:6px 8px;text-align:right">
              <button
                @click="quickLogin(u)"
                :disabled="loading"
                style="padding:3px 12px;background:#1e3a5f;color:#fff;border:none;border-radius:3px;cursor:pointer;font-size:.8em"
              >{{ t('login.submit') }}</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '../stores/auth.js'
import api from '../stores/api.js'

const { t, locale } = useI18n()
const auth = useAuthStore()
const router = useRouter()
const form = ref({ username: '', password: '' })
const loading = ref(false)
const error = ref('')
const demoUsers = ref([])

function setLocale(lang) {
  locale.value = lang
  localStorage.setItem('locale', lang)
}

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

async function quickLogin(user) {
  form.value.username = user.username
  form.value.password = user.password
  await submit()
}

onMounted(async () => {
  try {
    const res = await api.get('/auth/demo-users')
    demoUsers.value = res.data
  } catch {
    // silently ignore — list is optional
  }
})
</script>

<style>
.lang-switcher { display: flex; gap: 2px; }
.lang-btn {
  padding: 2px 8px; border: 1px solid rgba(30,58,95,.4); border-radius: 3px;
  background: transparent; color: #1e3a5f; cursor: pointer; font-size: .8em;
}
.lang-btn--active { background: #1e3a5f; color: #fff; border-color: #1e3a5f; }
</style>
