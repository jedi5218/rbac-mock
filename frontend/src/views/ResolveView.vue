<template>
  <div>
    <h2 style="margin-bottom:16px">Resolve Effective Permissions</h2>
    <div style="background:#fff;border-radius:8px;padding:20px;box-shadow:0 1px 4px rgba(0,0,0,.1);margin-bottom:20px">
      <div style="display:flex;gap:12px;align-items:flex-end">
        <div style="flex:1">
          <label style="font-weight:500;display:block;margin-bottom:6px">Select User</label>
          <select v-model="selectedUserId" style="width:100%;padding:8px;border:1px solid #ccc;border-radius:4px">
            <option value="">— choose user —</option>
            <option v-for="u in users" :key="u.id" :value="u.id">{{ u.username }} ({{ orgName(u.org_id) }})</option>
          </select>
        </div>
        <button @click="resolve" :disabled="!selectedUserId || loading" style="padding:8px 18px;background:#1e3a5f;color:#fff;border:none;border-radius:4px;cursor:pointer">
          Resolve
        </button>
      </div>
    </div>

    <div v-if="result" style="background:#fff;border-radius:8px;padding:20px;box-shadow:0 1px 4px rgba(0,0,0,.1)">
      <h3 style="margin-bottom:16px">Effective Permissions for <em>{{ resolvedUsername }}</em></h3>

      <div v-if="!result.permissions.length" style="color:#888;padding:16px;text-align:center">
        No permissions (user has no roles or roles have no resource permissions)
      </div>

      <table v-else style="width:100%;border-collapse:collapse">
        <thead>
          <tr style="background:#f0f4f8">
            <th style="padding:10px;text-align:left">Resource</th>
            <th style="padding:10px;text-align:left">Type</th>
            <th style="padding:10px;text-align:left">Bits</th>
            <th style="padding:10px;text-align:left">Effective Permissions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="p in result.permissions" :key="p.resource_id" style="border-top:1px solid #eee">
            <td style="padding:10px;font-weight:500">{{ p.resource_name }}</td>
            <td style="padding:10px">
              <span :style="`padding:2px 8px;border-radius:10px;font-size:.85em;background:${p.resource_type==='document'?'#e3f2fd':'#fce4ec'}`">{{ p.resource_type }}</span>
            </td>
            <td style="padding:10px;font-family:monospace;font-size:1.1em">{{ p.permission_bits }}</td>
            <td style="padding:10px">
              <span v-for="label in p.permission_labels" :key="label"
                    style="display:inline-block;margin-right:6px;padding:2px 8px;background:#e8f5e9;color:#2e7d32;border-radius:10px;font-size:.85em">
                {{ label }}
              </span>
            </td>
          </tr>
        </tbody>
      </table>

      <div style="margin-top:16px;padding:12px;background:#f8f9fb;border-radius:6px;font-size:.85em;color:#555">
        Computed via recursive role-tree CTE with BIT_OR aggregation across all transitively included roles.
      </div>
    </div>

    <p v-if="err" style="color:red;margin-top:12px">{{ err }}</p>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '../stores/api.js'

const users = ref([])
const orgs = ref([])
const selectedUserId = ref('')
const result = ref(null)
const loading = ref(false)
const err = ref('')

const resolvedUsername = computed(() => users.value.find(u => u.id === selectedUserId.value)?.username || '')
function orgName(id) { return orgs.value.find(o => o.id === id)?.name || id }

async function load() {
  const [u, o] = await Promise.all([api.get('/users/'), api.get('/orgs/')])
  users.value = u.data
  orgs.value = o.data
}

async function resolve() {
  err.value = ''
  result.value = null
  loading.value = true
  try {
    const res = await api.get(`/resolve/user/${selectedUserId.value}`)
    result.value = res.data
  } catch (e) {
    err.value = e.response?.data?.detail || 'Error resolving permissions'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>
