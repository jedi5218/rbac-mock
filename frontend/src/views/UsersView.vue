<template>
  <div>
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:16px">
      <h2 style="margin:0">{{ t('users.title') }}</h2>
      <router-link to="/wiki/users" class="help-link" :title="t('common.help')">?</router-link>
    </div>

    <!-- Org tree with users -->
    <div class="card" style="padding:8px">
      <div v-if="!orgs.length" style="color:#888;padding:8px;font-size:.9em">{{ t('users.noUsers') }}</div>
      <template v-else>
        <OrgUserNode
          v-for="root in roots"
          :key="root.id"
          :org="root"
          :depth="0"
          :children-of="childrenOf"
          :users-for-org="usersForOrg"
          :collapsed-orgs="collapsedOrgs"
          :toggle-org="toggleOrg"
          :auth="auth"
          :t="t"
          :open-create="openCreate"
          :open-edit="openEdit"
          :open-roles="openRoles"
          :delete-user="deleteUser"
        />
      </template>
    </div>

    <!-- Create user modal -->
    <div v-if="showCreate" class="modal-backdrop">
      <div class="modal">
        <h3>{{ t('users.createTitle') }}</h3>
        <label>{{ t('login.username') }}</label>
        <input v-model="createForm.username" class="field" />
        <label>{{ t('users.description') }}</label>
        <input v-model="createForm.description" class="field" :placeholder="t('users.descriptionHint')" />
        <label>{{ t('users.password') }}</label>
        <input type="password" v-model="createForm.password" class="field" />
        <label>{{ t('common.org') }}</label>
        <input :value="orgName(createForm.org_id)" class="field" disabled />
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
        <label>{{ t('users.description') }}</label>
        <input v-model="editForm.description" class="field" :placeholder="t('users.descriptionHint')" />
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
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '../stores/auth.js'
import api from '../stores/api.js'

const { t } = useI18n()
const auth = useAuthStore()
const users    = ref([])
const orgs     = ref([])
const allRoles = ref([])

const showCreate = ref(false)
const createForm = ref({ username: '', description: '', password: '', org_id: '', is_superadmin: false, is_org_admin: false })
const createErr  = ref('')

const editTarget = ref(null)
const editForm   = ref({ username: '', description: '', password: '', org_id: '', is_superadmin: false, is_org_admin: false })
const editErr    = ref('')

const roleTarget      = ref(null)
const assignedRoleIds = ref([])
const selectedRoleId  = ref('')
const roleErr         = ref('')

function orgName(id) { return orgs.value.find(o => o.id === id)?.name || id }

// ── Org tree helpers ──────────────────────────────────────────────────────
const collapsedOrgs = ref(new Set())
const roots = computed(() => orgs.value.filter(o => !o.parent_id))
function childrenOf(orgId) { return orgs.value.filter(o => o.parent_id === orgId) }
function toggleOrg(orgId) {
  const s = new Set(collapsedOrgs.value)
  s.has(orgId) ? s.delete(orgId) : s.add(orgId)
  collapsedOrgs.value = s
}
function usersForOrg(orgId) { return users.value.filter(u => u.org_id === orgId) }

// ── Data loading ──────────────────────────────────────────────────────────
async function load() {
  const [u, o, r] = await Promise.all([api.get('/users/'), api.get('/orgs/'), api.get('/roles/')])
  users.value    = u.data
  orgs.value     = o.data
  allRoles.value = r.data
}

function openCreate(orgId) {
  createErr.value = ''
  createForm.value = { username: '', description: '', password: '', org_id: orgId, is_superadmin: false, is_org_admin: false }
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
    description: user.description ?? '',
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
    description: editForm.value.description,
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

async function deleteUser(user) {
  if (!confirm(`Delete user "${user.username}"?`)) return
  try {
    await api.delete(`/users/${user.id}`)
    await load()
  } catch (e) { alert(e.response?.data?.detail || 'Error') }
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

<script>
import { defineComponent, h } from 'vue'

const OrgUserNode = defineComponent({
  name: 'OrgUserNode',
  props: ['org', 'depth', 'childrenOf', 'usersForOrg', 'collapsedOrgs', 'toggleOrg', 'auth', 't', 'openCreate', 'openEdit', 'openRoles', 'deleteUser'],
  setup(props) {
    return () => {
      const { org, depth, childrenOf, usersForOrg, collapsedOrgs, toggleOrg, auth, t, openCreate, openEdit, openRoles, deleteUser } = props
      const children = childrenOf(org.id)
      const orgUsers = usersForOrg(org.id)
      const isCollapsed = collapsedOrgs.has(org.id)
      const hasContent = children.length > 0 || orgUsers.length > 0

      const header = h('div', {
        class: 'org-header',
        style: `padding-left:${depth * 20 + 8}px`,
      }, [
        h('span', {
          onClick: () => toggleOrg(org.id),
          style: 'cursor:pointer;color:#888;width:14px;text-align:center;user-select:none;flex-shrink:0',
        }, hasContent ? (isCollapsed ? '▸' : '▾') : '•'),
        h('span', { class: 'org-header-name' }, org.name),
        auth.isSuperadmin
          ? h('button', {
              class: 'org-add-btn',
              onClick: (e) => { e.stopPropagation(); openCreate(org.id) },
            }, '+')
          : null,
      ])

      if (isCollapsed) return h('div', [header])

      const userRows = orgUsers.map(u =>
        h('div', {
          key: u.id,
          class: 'user-row',
          style: `padding-left:${depth * 20 + 30}px`,
        }, [
          h('div', { style: 'flex:1;min-width:0' }, [
            h('div', { style: 'display:flex;align-items:center;gap:6px' }, [
              h('span', { style: 'font-weight:500' }, u.username),
              u.is_superadmin ? h('span', { class: 'flag flag--super' }, t('users.superadmin')) : null,
              u.is_org_admin ? h('span', { class: 'flag flag--admin' }, t('users.orgAdmin')) : null,
            ]),
            u.description
              ? h('div', { style: 'font-size:.78em;color:#888;overflow:hidden;text-overflow:ellipsis;white-space:nowrap' }, u.description)
              : null,
          ]),
          auth.isAdmin
            ? h('div', { style: 'display:flex;gap:4px;flex-shrink:0' }, [
                h('button', { class: 'btn-sm-outline', onClick: () => openEdit(u) }, t('common.edit')),
                h('button', { class: 'btn-sm-outline', onClick: () => openRoles(u) }, t('users.rolesBtn')),
                u.id !== auth.user?.id
                  ? h('button', { class: 'btn-sm-danger', onClick: () => deleteUser(u) }, t('common.delete'))
                  : null,
              ])
            : null,
        ])
      )

      const childNodes = children.map(child =>
        h(OrgUserNode, {
          key: child.id,
          org: child,
          depth: depth + 1,
          childrenOf, usersForOrg, collapsedOrgs, toggleOrg, auth, t, openCreate, openEdit, openRoles, deleteUser,
        })
      )

      return h('div', [header, ...userRows, ...childNodes])
    }
  },
})

export default { components: { OrgUserNode } }
</script>

<style scoped>
.card { background:#fff; border-radius:8px; box-shadow:0 1px 4px rgba(0,0,0,.1); }

.org-header {
  display:flex; align-items:center; gap:8px; padding:8px 10px;
  background:#f0f4f8; border-radius:4px; margin-bottom:2px; font-size:.9em;
}
.org-header-name { font-weight:600; flex:1; color:#1e3a5f; }
.org-add-btn {
  width:22px; height:22px; border-radius:50%; background:#1e3a5f; color:#fff;
  border:none; cursor:pointer; font-size:1em; line-height:1; display:flex;
  align-items:center; justify-content:center; flex-shrink:0;
}
.org-add-btn:hover { background:#2a4a72; }

.user-row {
  display:flex; align-items:center; gap:8px; padding:6px 10px; margin-bottom:1px;
  border-bottom:1px solid #f5f5f5;
}
.user-row:hover { background:#fafbfc; }

.flag { padding:1px 6px; border-radius:10px; font-size:.75em; font-weight:600; }
.flag--super { background:#1e3a5f; color:#fff; }
.flag--admin { background:#2e7d32; color:#fff; }

.btn-sm-outline { padding:2px 8px; font-size:.8em; cursor:pointer; border:1px solid #1e3a5f; border-radius:3px; background:#fff; color:#1e3a5f; }
.btn-sm-danger  { padding:2px 8px; font-size:.8em; cursor:pointer; border:1px solid #e55; border-radius:3px; background:#fff; color:#e55; }

.modal-backdrop { position:fixed;inset:0;background:rgba(0,0,0,.4);display:flex;align-items:center;justify-content:center;z-index:100 }
.modal { background:#fff;border-radius:8px;padding:24px;width:420px;max-width:95vw }
.modal h3 { margin:0 0 16px }
.field { display:block;width:100%;padding:6px;margin:4px 0 12px;border:1px solid #ccc;border-radius:4px;box-sizing:border-box }
.field:disabled { background:#f5f5f5; color:#888; }
.btn-cancel { padding:6px 14px;border:1px solid #ccc;border-radius:4px;cursor:pointer;background:#fff }
.btn-primary { padding:6px 14px;background:#1e3a5f;color:#fff;border:none;border-radius:4px;cursor:pointer }
.help-link {
  display: inline-flex; align-items: center; justify-content: center;
  width: 18px; height: 18px; border-radius: 50%; background: #1e3a5f; color: #fff;
  font-size: .75em; font-weight: 700; text-decoration: none; flex-shrink: 0;
}
</style>
