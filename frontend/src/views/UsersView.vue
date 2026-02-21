<template>
  <div>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
      <div style="display:flex;align-items:center;gap:10px">
        <h2 style="margin:0">{{ t('users.title') }}</h2>
        <router-link to="/wiki/users" class="help-link" :title="t('common.help')">?</router-link>
      </div>
      <button v-if="auth.isSuperadmin" @click="openCreate" style="padding:6px 14px;background:#1e3a5f;color:#fff;border:none;border-radius:4px;cursor:pointer">{{ t('users.new') }}</button>
    </div>

    <table style="width:100%;background:#fff;border-radius:8px;border-collapse:collapse;box-shadow:0 1px 4px rgba(0,0,0,.1)">
      <thead>
        <tr style="background:#f0f4f8">
          <th style="padding:10px;text-align:left">{{ t('login.username') }}</th>
          <th style="padding:10px;text-align:left">{{ t('users.email') }}</th>
          <th style="padding:10px;text-align:left">{{ t('common.org') }}</th>
          <th style="padding:10px;text-align:left">{{ t('users.flags') }}</th>
          <th style="padding:10px;text-align:left">{{ t('common.actions') }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="u in users" :key="u.id" style="border-top:1px solid #eee">
          <td style="padding:10px">{{ u.username }}</td>
          <td style="padding:10px">{{ u.email }}</td>
          <td style="padding:10px">{{ orgName(u.org_id) }}</td>
          <td style="padding:10px">
            <span v-if="u.is_superadmin" style="background:#1e3a5f;color:#fff;padding:2px 6px;border-radius:10px;font-size:.8em;margin-right:4px">{{ t('users.superadmin') }}</span>
            <span v-if="u.is_org_admin" style="background:#2e7d32;color:#fff;padding:2px 6px;border-radius:10px;font-size:.8em">{{ t('users.orgAdmin') }}</span>
          </td>
          <td style="padding:10px;display:flex;gap:6px">
            <button v-if="auth.isAdmin" @click="openEdit(u)" style="padding:2px 8px;font-size:.85em;cursor:pointer;border:1px solid #1e3a5f;border-radius:3px;background:#fff;color:#1e3a5f">{{ t('common.edit') }}</button>
            <button v-if="auth.isAdmin" @click="openRoles(u)" style="padding:2px 8px;font-size:.85em;cursor:pointer;border:1px solid #555;border-radius:3px;background:#fff;color:#555">{{ t('users.rolesBtn') }}</button>
          </td>
        </tr>
        <tr v-if="!users.length">
          <td colspan="5" style="padding:16px;text-align:center;color:#888">{{ t('users.noUsers') }}</td>
        </tr>
      </tbody>
    </table>

    <!-- Create user modal -->
    <div v-if="showCreate" class="modal-backdrop">
      <div class="modal">
        <h3>{{ t('users.createTitle') }}</h3>
        <label>{{ t('login.username') }}</label>
        <input v-model="createForm.username" class="field" />
        <label>{{ t('users.email') }}</label>
        <input v-model="createForm.email" class="field" />
        <label>{{ t('users.password') }}</label>
        <input type="password" v-model="createForm.password" class="field" />
        <label>{{ t('common.org') }}</label>
        <select v-model="createForm.org_id" class="field">
          <option v-for="o in orgs" :key="o.id" :value="o.id">{{ o.name }}</option>
        </select>
        <div style="display:flex;gap:12px;margin-bottom:12px">
          <label><input type="checkbox" v-model="createForm.is_superadmin" /> {{ t('users.isSuperadmin') }}</label>
          <label><input type="checkbox" v-model="createForm.is_org_admin" /> {{ t('users.isOrgAdmin') }}</label>
        </div>
        <div style="display:flex;gap:8px;justify-content:flex-end">
          <button @click="showCreate=false" class="btn-cancel">{{ t('common.cancel') }}</button>
          <button @click="createUser" class="btn-primary">{{ t('common.create') }}</button>
        </div>
        <p v-if="createErr" style="color:red;margin-top:8px">{{ createErr }}</p>
      </div>
    </div>

    <!-- Edit user modal -->
    <div v-if="editTarget" class="modal-backdrop">
      <div class="modal">
        <h3>{{ t('users.editTitle') }} — {{ editTarget.username }}</h3>
        <label>{{ t('login.username') }}</label>
        <input v-model="editForm.username" class="field" />
        <label>{{ t('users.email') }}</label>
        <input v-model="editForm.email" class="field" />
        <label>{{ t('users.newPassword') }} <small style="color:#888">{{ t('users.keepBlank') }}</small></label>
        <input type="password" v-model="editForm.password" class="field" placeholder="unchanged" />
        <template v-if="auth.isSuperadmin">
          <label>{{ t('common.org') }}</label>
          <select v-model="editForm.org_id" class="field">
            <option v-for="o in orgs" :key="o.id" :value="o.id">{{ o.name }}</option>
          </select>
          <div style="display:flex;gap:12px;margin-bottom:12px">
            <label><input type="checkbox" v-model="editForm.is_superadmin" /> {{ t('users.isSuperadmin') }}</label>
            <label><input type="checkbox" v-model="editForm.is_org_admin" /> {{ t('users.isOrgAdmin') }}</label>
          </div>
        </template>
        <template v-else-if="auth.isAdmin">
          <div style="margin-bottom:12px">
            <label><input type="checkbox" v-model="editForm.is_org_admin" /> {{ t('users.isOrgAdmin') }}</label>
          </div>
        </template>
        <p v-if="editErr" style="color:red;margin-top:8px">{{ editErr }}</p>
        <div style="display:flex;gap:8px;justify-content:flex-end">
          <button @click="editTarget=null" class="btn-cancel">{{ t('common.cancel') }}</button>
          <button @click="saveEdit" class="btn-primary">{{ t('common.save') }}</button>
        </div>
      </div>
    </div>

    <!-- Roles assignment modal -->
    <div v-if="roleTarget" class="modal-backdrop">
      <div class="modal" style="width:480px">
        <h3>{{ t('users.manageRoles') }} — {{ roleTarget.username }}</h3>
        <p style="margin-bottom:12px;font-size:.9em;color:#555">{{ t('users.assignedRoles') }}</p>
        <div v-if="!assignedRoleIds.length" style="color:#888;margin-bottom:12px">{{ t('users.noRoles') }}</div>
        <div v-for="r in allRoles.filter(r => assignedRoleIds.includes(r.id))" :key="r.id"
             style="display:flex;justify-content:space-between;align-items:center;padding:6px 10px;background:#f0f4f8;border-radius:4px;margin-bottom:6px">
          <span>{{ r.name }} <small style="color:#888">({{ orgName(r.org_id) }})</small></span>
          <button @click="revokeRole(r.id)" style="padding:2px 8px;font-size:.8em;cursor:pointer;border:1px solid #e55;border-radius:3px;background:#fff;color:#e55">Revoke</button>
        </div>
        <hr style="margin:12px 0" />
        <p style="margin-bottom:8px;font-size:.9em;color:#555">{{ t('users.assignRole') }}</p>
        <div style="display:flex;gap:8px">
          <select v-model="selectedRoleId" style="flex:1;padding:6px;border:1px solid #ccc;border-radius:4px">
            <option value="">{{ t('users.selectRole') }}</option>
            <option v-for="r in allRoles.filter(r => !assignedRoleIds.includes(r.id) && !r.is_org_role)" :key="r.id" :value="r.id">
              {{ r.name }} ({{ orgName(r.org_id) }})
            </option>
          </select>
          <button @click="assignRole" :disabled="!selectedRoleId" style="padding:6px 12px;background:#1e3a5f;color:#fff;border:none;border-radius:4px;cursor:pointer">{{ t('common.add') }}</button>
        </div>
        <p v-if="roleErr" style="color:red;margin-top:8px">{{ roleErr }}</p>
        <div style="text-align:right;margin-top:16px">
          <button @click="roleTarget=null" class="btn-cancel">{{ t('common.close') }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '../stores/auth.js'
import api from '../stores/api.js'

const { t } = useI18n()
const auth = useAuthStore()
const users    = ref([])
const orgs     = ref([])
const allRoles = ref([])

const showCreate = ref(false)
const createForm = ref({ username: '', email: '', password: '', org_id: '', is_superadmin: false, is_org_admin: false })
const createErr  = ref('')

const editTarget = ref(null)
const editForm   = ref({ username: '', email: '', password: '', org_id: '', is_superadmin: false, is_org_admin: false })
const editErr    = ref('')

const roleTarget      = ref(null)
const assignedRoleIds = ref([])
const selectedRoleId  = ref('')
const roleErr         = ref('')

function orgName(id) { return orgs.value.find(o => o.id === id)?.name || id }

async function load() {
  const [u, o, r] = await Promise.all([api.get('/users/'), api.get('/orgs/'), api.get('/roles/')])
  users.value    = u.data
  orgs.value     = o.data
  allRoles.value = r.data
}

function openCreate() {
  createErr.value = ''
  createForm.value = { username: '', email: '', password: '', org_id: orgs.value[0]?.id ?? '', is_superadmin: false, is_org_admin: false }
  showCreate.value = true
}

async function createUser() {
  createErr.value = ''
  try {
    await api.post('/users/', createForm.value)
    showCreate.value = false
    await load()
  } catch (e) { createErr.value = e.response?.data?.detail || 'Error' }
}

function openEdit(user) {
  editErr.value = ''
  editTarget.value = user
  editForm.value = {
    username: user.username,
    email: user.email,
    password: '',
    org_id: user.org_id,
    is_superadmin: user.is_superadmin,
    is_org_admin: user.is_org_admin,
  }
}

async function saveEdit() {
  editErr.value = ''
  const body = {
    username: editForm.value.username,
    email: editForm.value.email,
    is_org_admin: editForm.value.is_org_admin,
  }
  if (editForm.value.password) body.password = editForm.value.password
  if (auth.isSuperadmin) {
    body.org_id = editForm.value.org_id
    body.is_superadmin = editForm.value.is_superadmin
  }
  try {
    await api.put(`/users/${editTarget.value.id}`, body)
    editTarget.value = null
    await load()
  } catch (e) { editErr.value = e.response?.data?.detail || 'Error' }
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
.modal h3 { margin:0 0 16px }
.field { display:block;width:100%;padding:6px;margin:4px 0 12px;border:1px solid #ccc;border-radius:4px;box-sizing:border-box }
.btn-cancel { padding:6px 14px;border:1px solid #ccc;border-radius:4px;cursor:pointer;background:#fff }
.btn-primary { padding:6px 14px;background:#1e3a5f;color:#fff;border:none;border-radius:4px;cursor:pointer }
.help-link {
  display: inline-flex; align-items: center; justify-content: center;
  width: 18px; height: 18px; border-radius: 50%; background: #1e3a5f; color: #fff;
  font-size: .75em; font-weight: 700; text-decoration: none; flex-shrink: 0;
}
</style>
