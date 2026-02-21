<template>
  <div>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
      <div style="display:flex;align-items:center;gap:10px">
        <h2 style="margin:0">{{ t('roles.title') }}</h2>
        <router-link to="/wiki/roles" class="help-link" :title="t('common.help')">?</router-link>
      </div>
      <button v-if="auth.isAdmin" @click="showCreate=true" class="btn-primary">{{ t('roles.new') }}</button>
    </div>

    <div style="display:grid;grid-template-columns:260px 1fr;gap:16px;align-items:start">
      <!-- ── Role list ────────────────────────────────────── -->
      <div class="card" style="padding:8px">
        <div
          v-for="r in roles" :key="r.id"
          @click="selectRole(r)"
          :class="['role-item', selected?.id === r.id && 'role-item--active']"
        >
          <div style="display:flex;align-items:center;gap:6px">
            <span style="font-weight:500">{{ r.name }}</span>
            <span v-if="r.is_org_role" class="badge badge--sys" title="Auto-managed org-member role">org</span>
            <span v-if="r.is_public && !r.is_org_role" class="badge badge--pub" title="Public role">pub</span>
          </div>
          <div style="font-size:.78em;color:#888">{{ orgName(r.org_id) }}</div>
        </div>
        <div v-if="!roles.length" style="color:#888;padding:8px;font-size:.9em">{{ t('roles.noRoles') }}</div>
      </div>

      <!-- ── Role detail ─────────────────────────────────── -->
      <div v-if="selected" class="card" style="padding:20px">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px">
          <h3 style="margin:0;display:flex;align-items:center;gap:8px">
            {{ selected.name }}
            <span v-if="selected.is_org_role" class="badge badge--sys">{{ t('roles.orgMember') }}</span>
            <span style="font-weight:normal;color:#888;font-size:.75em">{{ orgName(selected.org_id) }}</span>
          </h3>
          <div style="display:flex;align-items:center;gap:10px">
            <!-- is_public pill toggle (hidden for org-roles) -->
            <div v-if="!selected.is_org_role && auth.isAdmin" class="pill-toggle" :title="t('roles.publicHint')" @click="togglePublic">
              <div :class="['pill-track', selected.is_public && 'pill-track--on']">
                <div class="pill-thumb"></div>
              </div>
              <span class="pill-label">{{ selected.is_public ? t('roles.public') : t('roles.private') }}</span>
            </div>
            <span v-if="selected.is_org_role" class="badge badge--pub" style="font-size:.8em">{{ t('roles.alwaysPublic') }}</span>
            <button v-if="auth.isAdmin && !selected.is_org_role" @click="deleteRole(selected)" class="btn-danger-outline">{{ t('common.delete') }}</button>
          </div>
        </div>

        <!-- Org-role notice -->
        <div v-if="selected.is_org_role" style="background:#fffde7;border:1px solid #f9a825;border-radius:6px;padding:10px 14px;margin-bottom:16px;font-size:.875em;color:#555">
          {{ t('roles.orgMemberNotice', { org: orgName(selected.org_id) }) }}
        </div>

        <!-- ── 1. Users with this role ───────────────────── -->
        <section class="detail-section">
          <h4 class="section-title">
            {{ t('roles.usersTitle') }}
            <span v-if="selected.is_org_role" style="font-size:.8em;font-weight:normal;color:#888">{{ t('roles.autoManaged', { org: orgName(selected.org_id) }) }}</span>
          </h4>
          <div v-if="!roleUsers.length" class="empty-msg">{{ t('roles.noUsers') }}</div>
          <div v-else style="display:flex;flex-wrap:wrap;gap:6px">
            <span
              v-for="u in roleUsers" :key="u.id"
              class="chip chip--user"
              :title="orgName(u.org_id)"
            >{{ u.username }}</span>
          </div>
        </section>

        <!-- ── 2. Included roles (this role inherits from) ── -->
        <section class="detail-section">
          <h4 class="section-title">{{ t('roles.includedTitle') }} <span class="section-sub">{{ t('roles.includedSub') }}</span></h4>
          <div v-if="!inclusions.length" class="empty-msg">None</div>
          <div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:8px">
            <span v-for="r in inclusions" :key="r.id" class="chip chip--role">
              {{ formatRole(r) }}<span v-if="isForeign(r)" class="badge badge--foreign">{{ t('roles.foreign') }}</span>
              <button v-if="auth.isAdmin" @click="removeInclusion(r.id)" class="chip-remove" title="Remove">×</button>
            </span>
          </div>
          <div v-if="auth.isAdmin" style="display:flex;gap:8px">
            <select v-model="newIncId" class="select-sm">
              <option value="">{{ t('roles.addIncluded') }}</option>
              <option
                v-for="r in roles.filter(r => r.id !== selected.id && !inclusions.find(i => i.id === r.id))"
                :key="r.id" :value="r.id"
              >{{ isForeign(r) ? '⊕ ' : '' }}{{ formatRole(r) }}</option>
            </select>
            <button @click="addInclusion" :disabled="!newIncId" class="btn-sm btn-primary">{{ t('common.add') }}</button>
          </div>
          <p v-if="incErr" class="err-msg">{{ incErr }}</p>
        </section>

        <!-- ── 3. Parent roles (roles that include this role) -->
        <section v-if="!selected.is_org_role" class="detail-section">
          <h4 class="section-title">{{ t('roles.parentsTitle') }} <span class="section-sub">{{ t('roles.parentsSub') }}</span></h4>
          <div v-if="!parents.length" class="empty-msg">None</div>
          <div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:8px">
            <span v-for="r in parents" :key="r.id" class="chip chip--parent">
              {{ formatRole(r) }}<span v-if="isForeign(r)" class="badge badge--foreign">{{ t('roles.foreign') }}</span>
              <button v-if="auth.isAdmin" @click="removeParent(r.id)" class="chip-remove" title="Remove">×</button>
            </span>
          </div>
          <div v-if="auth.isAdmin" style="display:flex;gap:8px">
            <select v-model="newParentId" class="select-sm">
              <option value="">{{ t('roles.addParent') }}</option>
              <option
                v-for="r in parentCandidates.filter(r => r.id !== selected.id && !parents.find(p => p.id === r.id))"
                :key="r.id" :value="r.id"
              >{{ isForeign(r) ? '⊕ ' : '' }}{{ formatRole(r) }}</option>
            </select>
            <button @click="addParent" :disabled="!newParentId" class="btn-sm btn-primary">{{ t('common.add') }}</button>
          </div>
          <p v-if="parentErr" class="err-msg">{{ parentErr }}</p>
        </section>

        <!-- ── 4. Resource permissions (tri-state toggles) ── -->
        <section class="detail-section" style="border-bottom:none">
          <h4 class="section-title">{{ t('roles.permissionsTitle') }}</h4>

          <div class="perm-legend">
            <span class="perm-bit perm-bit--direct">{{ t('roles.permDirect') }}</span> {{ t('roles.permLegendDirect') }} &nbsp;·&nbsp;
            <span class="perm-bit perm-bit--inherited">{{ t('roles.permInherited') }}</span> {{ t('roles.permLegendInherited') }} &nbsp;·&nbsp;
            <span class="perm-bit perm-bit--off">{{ t('roles.permOff') }}</span> {{ t('roles.permLegendOff') }}
          </div>

          <div v-if="!roleResources.length" class="empty-msg">{{ t('roles.noResources') }}</div>
          <table v-else class="perm-table">
            <thead>
              <tr>
                <th>Resource</th>
                <th>Type</th>
                <th>Permissions</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="res in roleResources" :key="res.id">
                <td>{{ res.name }}</td>
                <td>
                  <span :class="['type-badge', res.resource_type === 'document' ? 'type-badge--doc' : 'type-badge--vid']">
                    {{ res.resource_type }}
                  </span>
                </td>
                <td>
                  <span
                    v-for="[bit, label] in bitsFor(res.resource_type)" :key="bit"
                    :class="['perm-bit', permBitClass(res.id, bit)]"
                    @click="auth.isAdmin && toggleBit(res, bit)"
                    :title="auth.isAdmin ? 'Click to toggle' : ''"
                    :style="auth.isAdmin ? 'cursor:pointer' : ''"
                  >{{ label }}</span>
                </td>
              </tr>
            </tbody>
          </table>
          <p v-if="permErr" class="err-msg">{{ permErr }}</p>
        </section>
      </div>

      <div v-else class="card" style="padding:40px;text-align:center;color:#aaa">
        {{ t('roles.selectRole') }}
      </div>
    </div>

    <!-- Create role modal -->
    <div v-if="showCreate" class="modal-backdrop">
      <div class="modal">
        <h3>{{ t('roles.createTitle') }}</h3>
        <label>{{ t('common.name') }}</label>
        <input v-model="form.name" class="field" />
        <label>{{ t('common.org') }}</label>
        <select v-model="form.org_id" class="field">
          <option v-for="o in orgs" :key="o.id" :value="o.id">{{ o.name }}</option>
        </select>
        <label style="display:flex;align-items:center;gap:8px;margin-bottom:14px;cursor:pointer">
          <input type="checkbox" v-model="form.is_public" />
          <span>{{ t('roles.public') }} <small style="color:#888">({{ t('roles.publicHint') }})</small></span>
        </label>
        <div style="display:flex;gap:8px;justify-content:flex-end">
          <button @click="showCreate=false" class="btn-cancel">{{ t('common.cancel') }}</button>
          <button @click="createRole" class="btn-primary">{{ t('common.create') }}</button>
        </div>
        <p v-if="err" class="err-msg">{{ err }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '../stores/auth.js'
import api from '../stores/api.js'

const { t } = useI18n()
const auth = useAuthStore()

// ── State ──────────────────────────────────────────────────────────────────
const roles            = ref([])
const parentCandidates = ref([])  // all public + in-scope roles, for parent dropdown
const orgs             = ref([])
const resources        = ref([])
const selected         = ref(null)
const inclusions = ref([])   // roles this role inherits from
const parents    = ref([])   // roles that include this role
const permissions      = ref([])   // direct: [{role_id, resource_id, permission_bits}]
const inheritedPerms   = ref({})   // {resource_id: bits} from included roles
const roleUsers        = ref([])   // users assigned this role

const showCreate  = ref(false)
const form        = ref({ name: '', org_id: '', is_public: false })
const newIncId    = ref('')
const newParentId = ref('')
const err         = ref('')
const incErr      = ref('')
const parentErr   = ref('')
const permErr     = ref('')

// ── Bit definitions ────────────────────────────────────────────────────────
const BITS = {
  document: [[1, 'read'], [2, 'write']],
  video:    [[1, 'view'], [2, 'comment'], [4, 'stream']],
}

function bitsFor(resourceType) {
  return BITS[resourceType] ?? []
}

// ── Helpers ────────────────────────────────────────────────────────────────
function orgName(id) { return orgs.value.find(o => o.id === id)?.name ?? id }

function formatRole(r) {
  const org = orgName(r.org_id)
  return r.is_org_role ? org : `${org}:${r.name}`
}

// Set of org IDs that are in the current user's own-org + ancestors + descendants.
// null means superadmin (nothing is foreign).
const hierarchyOrgIds = computed(() => {
  if (!auth.user || auth.user.is_superadmin) return null
  const all = orgs.value
  const inScope = new Set()
  // Own org + walk up to ancestors
  let cur = all.find(o => o.id === auth.user.org_id)
  while (cur) {
    inScope.add(cur.id)
    cur = cur.parent_id ? all.find(o => o.id === cur.parent_id) : null
  }
  // Descendants: BFS
  const queue = [auth.user.org_id]
  while (queue.length) {
    const pid = queue.shift()
    for (const c of all.filter(o => o.parent_id === pid)) {
      if (!inScope.has(c.id)) { inScope.add(c.id); queue.push(c.id) }
    }
  }
  return inScope
})

function isForeign(role) {
  return hierarchyOrgIds.value !== null && !hierarchyOrgIds.value.has(role.org_id)
}

function directBitsFor(resourceId) {
  return permissions.value.find(p => p.resource_id === resourceId)?.permission_bits ?? 0
}

function inheritedBitsFor(resourceId) {
  return inheritedPerms.value[resourceId] ?? 0
}

// Resources that belong to the selected role's own org
const roleResources = computed(() =>
  selected.value ? resources.value.filter(r => r.org_id === selected.value.org_id) : []
)

function permBitClass(resourceId, bit) {
  if (directBitsFor(resourceId) & bit)   return 'perm-bit--direct'
  if (inheritedBitsFor(resourceId) & bit) return 'perm-bit--inherited'
  return 'perm-bit--off'
}

// ── Data loading ───────────────────────────────────────────────────────────
async function load() {
  const [r, pc, o, res] = await Promise.all([
    api.get('/roles/'),
    api.get('/roles/?include_all_public=true'),
    api.get('/orgs/'),
    api.get('/resources/'),
  ])
  roles.value            = r.data
  parentCandidates.value = pc.data
  orgs.value             = o.data
  resources.value        = res.data
  if (!form.value.org_id && o.data.length) form.value.org_id = o.data[0].id
}

async function selectRole(r) {
  selected.value = r
  incErr.value = parentErr.value = permErr.value = ''
  newIncId.value = newParentId.value = ''
  await loadDetail(r.id)
}

async function loadDetail(id) {
  const [inc, par, perm, inh, users] = await Promise.all([
    api.get(`/roles/${id}/inclusions`),
    api.get(`/roles/${id}/parents`),
    api.get(`/roles/${id}/permissions`),
    api.get(`/roles/${id}/inherited-permissions`),
    api.get(`/roles/${id}/users`),
  ])
  inclusions.value    = inc.data
  parents.value       = par.data
  permissions.value   = perm.data
  inheritedPerms.value = inh.data
  roleUsers.value     = users.data
}

// ── Public toggle ──────────────────────────────────────────────────────────
async function togglePublic() {
  permErr.value = ''
  try {
    const res = await api.put(`/roles/${selected.value.id}`, { is_public: !selected.value.is_public })
    // update local state
    selected.value = res.data
    const idx = roles.value.findIndex(r => r.id === selected.value.id)
    if (idx !== -1) roles.value[idx] = res.data
  } catch (e) { permErr.value = e.response?.data?.detail ?? 'Error' }
}

// ── Role CRUD ──────────────────────────────────────────────────────────────
async function createRole() {
  err.value = ''
  try {
    await api.post('/roles/', form.value)
    showCreate.value = false
    form.value.name = ''
    await load()
  } catch (e) { err.value = e.response?.data?.detail ?? 'Error' }
}

async function deleteRole(role) {
  if (!confirm(`Delete role "${role.name}"?`)) return
  try {
    await api.delete(`/roles/${role.id}`)
    selected.value = null
    await load()
  } catch (e) { alert(e.response?.data?.detail ?? 'Error') }
}

// ── Inclusions ─────────────────────────────────────────────────────────────
async function addInclusion() {
  incErr.value = ''
  try {
    await api.post(`/roles/${selected.value.id}/inclusions`, { included_role_id: newIncId.value })
    newIncId.value = ''
    await loadDetail(selected.value.id)
  } catch (e) { incErr.value = e.response?.data?.detail ?? 'Error' }
}

async function removeInclusion(incId) {
  incErr.value = ''
  try {
    await api.delete(`/roles/${selected.value.id}/inclusions/${incId}`)
    await loadDetail(selected.value.id)
  } catch (e) { incErr.value = e.response?.data?.detail ?? 'Error' }
}

// ── Parent roles ───────────────────────────────────────────────────────────
async function addParent() {
  parentErr.value = ''
  try {
    await api.post(`/roles/${selected.value.id}/parents`, { parent_role_id: newParentId.value })
    newParentId.value = ''
    await loadDetail(selected.value.id)
  } catch (e) { parentErr.value = e.response?.data?.detail ?? 'Error' }
}

async function removeParent(parentId) {
  parentErr.value = ''
  try {
    await api.delete(`/roles/${selected.value.id}/parents/${parentId}`)
    await loadDetail(selected.value.id)
  } catch (e) { parentErr.value = e.response?.data?.detail ?? 'Error' }
}

// ── Permission toggles ─────────────────────────────────────────────────────
async function toggleBit(resource, bit) {
  permErr.value = ''
  const direct = directBitsFor(resource.id)
  const isOn   = !!(direct & bit)
  const newBits = isOn ? (direct & ~bit) : (direct | bit)
  try {
    if (newBits === 0) {
      await api.delete(`/roles/${selected.value.id}/permissions/${resource.id}`)
    } else {
      await api.put(`/roles/${selected.value.id}/permissions/${resource.id}`, { permission_bits: newBits })
    }
    await loadDetail(selected.value.id)
  } catch (e) { permErr.value = e.response?.data?.detail ?? 'Error' }
}

onMounted(load)
</script>

<style scoped>
.card { background:#fff; border-radius:8px; box-shadow:0 1px 4px rgba(0,0,0,.1); }

/* Role list */
.role-item {
  padding:10px 12px; border-radius:4px; cursor:pointer; margin-bottom:4px;
  border-left:3px solid transparent; transition:background .1s;
}
.role-item:hover { background:#f5f7fa; }
.role-item--active { border-left-color:#1e3a5f; background:#f0f4f8; }

/* Detail sections */
.detail-section {
  margin-bottom:20px; padding-bottom:20px; border-bottom:1px solid #eee;
}
.section-title { margin:0 0 10px; font-size:.9em; text-transform:uppercase; letter-spacing:.04em; color:#555; }
.section-sub { text-transform:none; letter-spacing:0; font-weight:normal; color:#888; font-size:.9em; }
.empty-msg { color:#aaa; font-size:.9em; margin-bottom:6px; }

/* Chips */
.chip {
  display:inline-flex; align-items:center; gap:4px;
  padding:3px 8px; border-radius:12px; font-size:.82em;
}
.chip--user   { background:#e8f5e9; color:#2e7d32; }
.chip--role   { background:#e3f2fd; color:#1565c0; }
.chip--parent { background:#fff3e0; color:#e65100; }
.chip-remove {
  background:none; border:none; cursor:pointer; font-size:1.1em; line-height:1;
  padding:0 1px; opacity:.6;
}
.chip-remove:hover { opacity:1; }

/* Permission toggles */
.perm-bit {
  display:inline-block; padding:3px 9px; border-radius:4px; font-size:.8em;
  margin-right:4px; margin-bottom:2px; user-select:none; transition:all .12s;
}
.perm-bit--direct    { background:#1e7e34; color:#fff; }
.perm-bit--inherited { background:transparent; border:1.5px solid #1565c0; color:#1565c0; }
.perm-bit--off       { background:#e9ecef; color:#aaa; border:1.5px solid transparent; }
.perm-bit--direct:hover    { background:#155724; }
.perm-bit--inherited:hover { background:#e3f2fd; }
.perm-bit--off:hover       { background:#dee2e6; color:#888; }

.perm-legend {
  font-size:.8em; color:#666; margin-bottom:10px;
  padding:8px 12px; background:#f8f9fb; border-radius:4px;
}

/* Permission table */
.perm-table { width:100%; border-collapse:collapse; }
.perm-table th { padding:8px 10px; text-align:left; font-size:.85em; background:#f0f4f8; }
.perm-table td { padding:8px 10px; border-top:1px solid #eee; vertical-align:middle; }

/* Type badges */
.type-badge { padding:2px 8px; border-radius:10px; font-size:.8em; }
.type-badge--doc { background:#e3f2fd; color:#1565c0; }
.type-badge--vid { background:#fce4ec; color:#c62828; }

/* Form helpers */
.select-sm { padding:5px 8px; border:1px solid #ccc; border-radius:4px; flex:1; font-size:.9em; }
.field { display:block; width:100%; padding:7px; margin:4px 0 14px; border:1px solid #ccc; border-radius:4px; }
.err-msg { color:#c00; font-size:.85em; margin-top:6px; }

/* Buttons */
.btn-primary  { padding:6px 14px; background:#1e3a5f; color:#fff; border:none; border-radius:4px; cursor:pointer; }
.btn-cancel   { padding:6px 14px; border:1px solid #ccc; border-radius:4px; cursor:pointer; background:#fff; }
.btn-danger-outline { padding:4px 10px; border:1px solid #c00; border-radius:4px; cursor:pointer; color:#c00; background:#fff; font-size:.85em; }
.btn-sm       { padding:5px 12px; border:none; border-radius:4px; cursor:pointer; font-size:.9em; }
.btn-sm:disabled { opacity:.4; cursor:default; }

/* Badges */
.badge { padding:1px 6px; border-radius:8px; font-size:.72em; font-weight:600; letter-spacing:.02em; }
.badge--sys     { background:#fff3e0; color:#e65100; }
.badge--pub     { background:#e8f5e9; color:#2e7d32; }
.badge--foreign { background:#fce4ec; color:#880e4f; margin-left:4px; }

/* Public pill toggle */
.pill-toggle { display:inline-flex; align-items:center; gap:7px; cursor:pointer; user-select:none; }
.pill-track {
  position:relative; width:38px; height:21px; background:#ccc;
  border-radius:11px; transition:background .2s; flex-shrink:0;
}
.pill-track--on { background:#2e7d32; }
.pill-thumb {
  position:absolute; top:2.5px; left:2.5px; width:16px; height:16px;
  background:#fff; border-radius:50%; transition:transform .2s;
  box-shadow:0 1px 3px rgba(0,0,0,.25);
}
.pill-track--on .pill-thumb { transform:translateX(17px); }
.pill-label { font-size:.85em; color:#444; }

/* Help link */
.help-link {
  display:inline-flex; align-items:center; justify-content:center;
  width:18px; height:18px; border-radius:50%; background:#1e3a5f; color:#fff;
  font-size:.75em; font-weight:700; text-decoration:none; flex-shrink:0;
}

/* Modal */
.modal-backdrop { position:fixed; inset:0; background:rgba(0,0,0,.4); display:flex; align-items:center; justify-content:center; z-index:100; }
.modal { background:#fff; border-radius:8px; padding:24px; width:380px; max-width:95vw; }
.modal h3 { margin:0 0 16px; }
</style>
