<template>
  <div>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
      <h2>Resources</h2>
      <button v-if="auth.isAdmin" @click="openCreate" class="btn-primary">+ New Resource</button>
    </div>

    <table class="main-table">
      <thead>
        <tr>
          <th>Name</th>
          <th>Type</th>
          <th>Org</th>
          <th v-if="auth.isAdmin">Actions</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="r in resources" :key="r.id">
          <td>{{ r.name }}</td>
          <td><span :class="['type-badge', r.resource_type === 'document' ? 'type-badge--doc' : 'type-badge--vid']">{{ r.resource_type }}</span></td>
          <td>{{ orgName(r.org_id) }}</td>
          <td v-if="auth.isAdmin" style="display:flex;gap:6px;padding:8px 10px">
            <button @click="openEdit(r)" class="btn-sm-outline">Edit</button>
            <button @click="deleteResource(r)" class="btn-sm-danger">Delete</button>
          </td>
        </tr>
        <tr v-if="!resources.length">
          <td :colspan="auth.isAdmin ? 4 : 3" class="empty-cell">No resources</td>
        </tr>
      </tbody>
    </table>

    <!-- Create / Edit modal -->
    <div v-if="showModal" class="modal-backdrop">
      <div class="modal">
        <h3>{{ editTarget ? 'Edit Resource' : 'Create Resource' }}</h3>

        <label>Name</label>
        <input v-model="form.name" class="field" />

        <label>Type</label>
        <select v-model="form.resource_type" class="field" :disabled="!!editTarget">
          <option value="document">document</option>
          <option value="video">video</option>
        </select>

        <label>Org</label>
        <select v-model="form.org_id" class="field" :disabled="!!editTarget">
          <option v-for="o in orgs" :key="o.id" :value="o.id">{{ o.name }}</option>
        </select>

        <!-- Role permissions for this resource -->
        <div v-if="orgRoles.length" style="margin-top:8px;margin-bottom:14px">
          <div style="font-size:.85em;font-weight:600;color:#555;text-transform:uppercase;letter-spacing:.04em;margin-bottom:8px">Role permissions</div>
          <div class="perm-legend">
            Click bits to toggle. Only roles in this resource's org are shown.
          </div>
          <table class="perm-table">
            <thead>
              <tr><th>Role</th><th>Permissions</th></tr>
            </thead>
            <tbody>
              <tr v-for="role in orgRoles" :key="role.id">
                <td style="font-size:.875em">{{ role.name }}</td>
                <td>
                  <span
                    v-for="[bit, label] in bitsFor(form.resource_type)" :key="bit"
                    :class="['perm-bit', (resPerms[role.id] ?? 0) & bit ? 'perm-bit--on' : 'perm-bit--off']"
                    @click="toggleResBit(role.id, bit)"
                    style="cursor:pointer"
                  >{{ label }}</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-else style="font-size:.85em;color:#aaa;margin-bottom:14px">No non-system roles in this org yet.</div>

        <p v-if="err" class="err-msg">{{ err }}</p>
        <div style="display:flex;gap:8px;justify-content:flex-end">
          <button @click="showModal=false" class="btn-cancel">Cancel</button>
          <button @click="saveModal" class="btn-primary">{{ editTarget ? 'Save' : 'Create' }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useAuthStore } from '../stores/auth.js'
import api from '../stores/api.js'

const auth = useAuthStore()
const resources = ref([])
const orgs      = ref([])
const allRoles  = ref([])

const showModal  = ref(false)
const editTarget = ref(null)   // null = create, resource obj = edit
const form       = ref({ name: '', resource_type: 'document', org_id: '' })
const resPerms   = ref({})     // { [role_id]: bits }
const origPerms  = ref({})     // bits as loaded from server (for diffing on save)
const err        = ref('')

const BITS = {
  document: [[1, 'read'], [2, 'write']],
  video:    [[1, 'view'], [2, 'comment'], [4, 'stream']],
}
function bitsFor(type) { return BITS[type] ?? [] }

function orgName(id) { return orgs.value.find(o => o.id === id)?.name ?? id }

// Non-org-role roles belonging to the selected org
const orgRoles = computed(() =>
  allRoles.value.filter(r => r.org_id === form.value.org_id && !r.is_org_role)
)

// Reset permissions when org changes in create mode
watch(() => form.value.org_id, () => {
  if (!editTarget.value) { resPerms.value = {}; origPerms.value = {} }
})

function toggleResBit(roleId, bit) {
  resPerms.value = { ...resPerms.value, [roleId]: (resPerms.value[roleId] ?? 0) ^ bit }
}

async function load() {
  const [r, o, roles] = await Promise.all([
    api.get('/resources/'),
    api.get('/orgs/'),
    api.get('/roles/'),
  ])
  resources.value = r.data
  orgs.value      = o.data
  allRoles.value  = roles.data
  if (!form.value.org_id && o.data.length) form.value.org_id = o.data[0].id
}

function openCreate() {
  editTarget.value = null
  form.value = { name: '', resource_type: 'document', org_id: orgs.value[0]?.id ?? '' }
  resPerms.value = {}
  origPerms.value = {}
  err.value = ''
  showModal.value = true
}

async function openEdit(resource) {
  editTarget.value = resource
  form.value = { name: resource.name, resource_type: resource.resource_type, org_id: resource.org_id }
  err.value = ''
  // Load existing role permissions for this resource
  const res = await api.get(`/resources/${resource.id}/permissions`)
  const p = {}
  for (const row of res.data) p[row.role_id] = row.permission_bits
  resPerms.value  = { ...p }
  origPerms.value = { ...p }
  showModal.value = true
}

async function saveModal() {
  err.value = ''
  try {
    let resourceId
    if (editTarget.value) {
      await api.put(`/resources/${editTarget.value.id}`, { name: form.value.name })
      resourceId = editTarget.value.id
    } else {
      const r = await api.post('/resources/', form.value)
      resourceId = r.data.id
    }
    // Sync permissions for all same-org roles
    await Promise.all(orgRoles.value.map(async role => {
      const bits = resPerms.value[role.id] ?? 0
      const orig = origPerms.value[role.id] ?? 0
      if (bits === orig) return
      if (bits > 0) {
        await api.put(`/roles/${role.id}/permissions/${resourceId}`, { permission_bits: bits })
      } else {
        await api.delete(`/roles/${role.id}/permissions/${resourceId}`)
      }
    }))
    showModal.value = false
    await load()
  } catch (e) { err.value = e.response?.data?.detail ?? 'Error' }
}

async function deleteResource(r) {
  if (!confirm(`Delete "${r.name}"?`)) return
  try {
    await api.delete(`/resources/${r.id}`)
    await load()
  } catch (e) { alert(e.response?.data?.detail ?? 'Error') }
}

onMounted(load)
</script>

<style scoped>
.main-table {
  width:100%; background:#fff; border-radius:8px; border-collapse:collapse;
  box-shadow:0 1px 4px rgba(0,0,0,.1);
}
.main-table th { padding:10px; text-align:left; background:#f0f4f8; font-size:.875em; }
.main-table td { padding:8px 10px; border-top:1px solid #eee; vertical-align:middle; }
.empty-cell { padding:16px; text-align:center; color:#888; }

.type-badge { padding:2px 8px; border-radius:10px; font-size:.85em; }
.type-badge--doc { background:#e3f2fd; color:#1565c0; }
.type-badge--vid { background:#fce4ec; color:#c62828; }

.perm-table { width:100%; border-collapse:collapse; margin-top:4px; }
.perm-table th { padding:6px 8px; text-align:left; font-size:.8em; background:#f0f4f8; }
.perm-table td { padding:6px 8px; border-top:1px solid #eee; vertical-align:middle; }

.perm-bit {
  display:inline-block; padding:2px 8px; border-radius:4px; font-size:.78em;
  margin-right:4px; user-select:none; transition:all .1s;
}
.perm-bit--on  { background:#1e7e34; color:#fff; }
.perm-bit--off { background:#e9ecef; color:#aaa; border:1px solid transparent; }
.perm-bit--on:hover  { background:#155724; }
.perm-bit--off:hover { background:#dee2e6; color:#888; }

.perm-legend {
  font-size:.78em; color:#888; margin-bottom:8px;
  padding:6px 10px; background:#f8f9fb; border-radius:4px;
}

.modal-backdrop { position:fixed; inset:0; background:rgba(0,0,0,.4); display:flex; align-items:center; justify-content:center; z-index:100; }
.modal { background:#fff; border-radius:8px; padding:24px; width:520px; max-width:95vw; max-height:90vh; overflow-y:auto; }
.modal h3 { margin:0 0 16px; }
.field { display:block; width:100%; padding:6px; margin:4px 0 12px; border:1px solid #ccc; border-radius:4px; box-sizing:border-box; }
.field:disabled { background:#f5f5f5; color:#888; }
.err-msg { color:#c00; font-size:.85em; margin-bottom:8px; }

.btn-primary  { padding:6px 14px; background:#1e3a5f; color:#fff; border:none; border-radius:4px; cursor:pointer; }
.btn-cancel   { padding:6px 14px; border:1px solid #ccc; border-radius:4px; cursor:pointer; background:#fff; }
.btn-sm-outline { padding:2px 8px; font-size:.85em; cursor:pointer; border:1px solid #1e3a5f; border-radius:3px; background:#fff; color:#1e3a5f; }
.btn-sm-danger  { padding:2px 8px; font-size:.85em; cursor:pointer; border:1px solid #e55; border-radius:3px; background:#fff; color:#e55; }
</style>
