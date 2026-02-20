<template>
  <div>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
      <h2>Users</h2>
      <button v-if="auth.isSuperadmin" @click="showCreate=true" style="padding:6px 14px;background:#1e3a5f;color:#fff;border:none;border-radius:4px;cursor:pointer">+ New User</button>
    </div>

    <table style="width:100%;background:#fff;border-radius:8px;border-collapse:collapse;box-shadow:0 1px 4px rgba(0,0,0,.1)">
      <thead>
        <tr style="background:#f0f4f8">
          <th style="padding:10px;text-align:left">Username</th>
          <th style="padding:10px;text-align:left">Email</th>
          <th style="padding:10px;text-align:left">Org</th>
          <th style="padding:10px;text-align:left">Flags</th>
          <th style="padding:10px;text-align:left">Actions</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="u in users" :key="u.id" style="border-top:1px solid #eee">
          <td style="padding:10px">{{ u.username }}</td>
          <td style="padding:10px">{{ u.email }}</td>
          <td style="padding:10px">{{ orgName(u.org_id) }}</td>
          <td style="padding:10px">
            <span v-if="u.is_superadmin" style="background:#1e3a5f;color:#fff;padding:2px 6px;border-radius:10px;font-size:.8em;margin-right:4px">superadmin</span>
            <span v-if="u.is_org_admin" style="background:#2e7d32;color:#fff;padding:2px 6px;border-radius:10px;font-size:.8em">org-admin</span>
          </td>
          <td style="padding:10px">
            <button v-if="auth.isAdmin" @click="openRoles(u)" style="padding:2px 8px;font-size:.85em;cursor:pointer;border:1px solid #1e3a5f;border-radius:3px;background:#fff;color:#1e3a5f;margin-right:4px">Roles</button>
          </td>
        </tr>
        <tr v-if="!users.length">
          <td colspan="5" style="padding:16px;text-align:center;color:#888">No users</td>
        </tr>
      </tbody>
    </table>

    <!-- Create user modal -->
    <div v-if="showCreate" class="modal-backdrop">
      <div class="modal">
        <h3>Create User</h3>
        <label>Username</label>
        <input v-model="form.username" class="field" />
        <label>Email</label>
        <input v-model="form.email" class="field" />
        <label>Password</label>
        <input type="password" v-model="form.password" class="field" />
        <label>Org</label>
        <select v-model="form.org_id" class="field">
          <option v-for="o in orgs" :key="o.id" :value="o.id">{{ o.name }}</option>
        </select>
        <div style="display:flex;gap:12px;margin-bottom:12px">
          <label><input type="checkbox" v-model="form.is_superadmin" /> Superadmin</label>
          <label><input type="checkbox" v-model="form.is_org_admin" /> Org Admin</label>
        </div>
        <div style="display:flex;gap:8px;justify-content:flex-end">
          <button @click="showCreate=false" class="btn-cancel">Cancel</button>
          <button @click="createUser" class="btn-primary">Create</button>
        </div>
        <p v-if="err" style="color:red;margin-top:8px">{{ err }}</p>
      </div>
    </div>

    <!-- Roles assignment modal -->
    <div v-if="roleTarget" class="modal-backdrop">
      <div class="modal" style="width:480px">
        <h3>Manage Roles — {{ roleTarget.username }}</h3>
        <p style="margin-bottom:12px;font-size:.9em;color:#555">Assigned roles:</p>
        <div v-if="!assignedRoleIds.length" style="color:#888;margin-bottom:12px">No roles assigned</div>
        <div v-for="r in allRoles.filter(r => assignedRoleIds.includes(r.id))" :key="r.id"
             style="display:flex;justify-content:space-between;align-items:center;padding:6px 10px;background:#f0f4f8;border-radius:4px;margin-bottom:6px">
          <span>{{ r.name }} <small style="color:#888">({{ orgName(r.org_id) }})</small></span>
          <button @click="revokeRole(r.id)" style="padding:2px 8px;font-size:.8em;cursor:pointer;border:1px solid #e55;border-radius:3px;background:#fff;color:#e55">Revoke</button>
        </div>
        <hr style="margin:12px 0" />
        <p style="margin-bottom:8px;font-size:.9em;color:#555">Assign role:</p>
        <div style="display:flex;gap:8px">
          <select v-model="selectedRoleId" style="flex:1;padding:6px;border:1px solid #ccc;border-radius:4px">
            <option value="">— select role —</option>
            <option v-for="r in allRoles.filter(r => !assignedRoleIds.includes(r.id))" :key="r.id" :value="r.id">
              {{ r.name }} ({{ orgName(r.org_id) }})
            </option>
          </select>
          <button @click="assignRole" :disabled="!selectedRoleId" style="padding:6px 12px;background:#1e3a5f;color:#fff;border:none;border-radius:4px;cursor:pointer">Assign</button>
        </div>
        <p v-if="roleErr" style="color:red;margin-top:8px">{{ roleErr }}</p>
        <div style="text-align:right;margin-top:16px">
          <button @click="roleTarget=null" class="btn-cancel">Close</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useAuthStore } from '../stores/auth.js'
import api from '../stores/api.js'

const auth = useAuthStore()
const users = ref([])
const orgs = ref([])
const allRoles = ref([])
const showCreate = ref(false)
const roleTarget = ref(null)
const assignedRoleIds = ref([])
const selectedRoleId = ref('')
const err = ref('')
const roleErr = ref('')
const form = ref({ username: '', email: '', password: '', org_id: '', is_superadmin: false, is_org_admin: false })

function orgName(id) { return orgs.value.find(o => o.id === id)?.name || id }

async function load() {
  const [u, o, r] = await Promise.all([api.get('/users/'), api.get('/orgs/'), api.get('/roles/')])
  users.value = u.data
  orgs.value = o.data
  allRoles.value = r.data
}

async function createUser() {
  err.value = ''
  try {
    await api.post('/users/', form.value)
    showCreate.value = false
    form.value = { username: '', email: '', password: '', org_id: '', is_superadmin: false, is_org_admin: false }
    await load()
  } catch (e) { err.value = e.response?.data?.detail || 'Error' }
}

async function openRoles(user) {
  roleTarget.value = user
  roleErr.value = ''
  selectedRoleId.value = ''
  await loadUserRoles(user.id)
}

async function loadUserRoles(userId) {
  const res = await api.get(`/users/${userId}/roles`)
  assignedRoleIds.value = res.data.map(r => r.id)
}

async function assignRole() {
  roleErr.value = ''
  try {
    await api.post(`/users/${roleTarget.value.id}/roles/${selectedRoleId.value}`)
    selectedRoleId.value = ''
    await loadUserRoles(roleTarget.value.id)
  } catch (e) { roleErr.value = e.response?.data?.detail || 'Error' }
}

async function revokeRole(roleId) {
  roleErr.value = ''
  try {
    await api.delete(`/users/${roleTarget.value.id}/roles/${roleId}`)
    await loadUserRoles(roleTarget.value.id)
  } catch (e) { roleErr.value = e.response?.data?.detail || 'Error' }
}

onMounted(load)
</script>

<style scoped>
.modal-backdrop { position:fixed;inset:0;background:rgba(0,0,0,.4);display:flex;align-items:center;justify-content:center;z-index:100 }
.modal { background:#fff;border-radius:8px;padding:24px;width:420px;max-width:95vw }
.modal h3 { margin-bottom:16px }
.field { display:block;width:100%;padding:6px;margin:4px 0 12px;border:1px solid #ccc;border-radius:4px }
.btn-cancel { padding:6px 14px;border:1px solid #ccc;border-radius:4px;cursor:pointer;background:#fff }
.btn-primary { padding:6px 14px;background:#1e3a5f;color:#fff;border:none;border-radius:4px;cursor:pointer }
</style>
