<template>
  <div>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
      <div style="display:flex;align-items:center;gap:10px">
        <h2 style="margin:0">{{ t('exchanges.title') }}</h2>
        <router-link to="/wiki/exchanges" class="help-link" :title="t('common.help')">?</router-link>
      </div>
      <button v-if="auth.isAdmin" @click="showCreate=true" class="btn-primary">{{ t('exchanges.new') }}</button>
    </div>

    <p style="color:#666;font-size:.9em;margin-bottom:20px">{{ t('exchanges.subtitle') }}</p>

    <div v-if="loading" style="color:#888;padding:20px">{{ t('common.loading') }}</div>

    <div v-else style="display:grid;grid-template-columns:320px 1fr;gap:16px;align-items:start">
      <!-- Left panel: exchanges grouped by partner org -->
      <div class="card" style="padding:8px">
        <div v-if="!groupedExchanges.length" style="color:#888;padding:8px;font-size:.9em">{{ t('exchanges.noExchanges') }}</div>
        <div v-for="group in groupedExchanges" :key="group.partnerOrgId" style="margin-bottom:6px">
          <div
            @click="group.open = !group.open"
            style="display:flex;align-items:center;gap:8px;padding:8px 10px;cursor:pointer;border-radius:4px;user-select:none"
            :style="{ background: group.open ? '#f0f4f8' : 'transparent' }"
          >
            <span style="font-size:.85em;opacity:.6;width:14px;text-align:center">{{ group.open ? '▾' : '▸' }}</span>
            <span style="font-weight:500;flex:1">{{ group.partnerOrgName }}</span>
            <span style="font-size:.75em;background:#e0e0e0;color:#444;padding:1px 7px;border-radius:10px">
              {{ group.totalRoles }} {{ t('exchanges.rolesLabel') }}
            </span>
          </div>
          <div v-if="group.open" style="margin-left:22px">
            <div
              v-for="ex in group.exchanges" :key="ex.id"
              @click="selectExchange(ex)"
              :class="['exchange-item', selected?.id === ex.id && 'exchange-item--active']"
            >
              <span style="font-size:.85em">{{ ex.ownOrgName }} ↔ {{ ex.partnerOrgName }}</span>
              <span style="font-size:.72em;color:#888">{{ ex.exposed_roles.length }} {{ t('exchanges.rolesLabel') }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Right panel: exchange detail -->
      <div v-if="selected" class="card" style="padding:20px">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px">
          <h3 style="margin:0">{{ orgName(selected.org_a_id) }} ↔ {{ orgName(selected.org_b_id) }}</h3>
          <div style="display:flex;align-items:center;gap:10px">
            <span style="font-size:.8em;color:#888">{{ t('exchanges.created') }}: {{ new Date(selected.created_at).toLocaleDateString() }}</span>
            <button v-if="auth.isAdmin" @click="confirmClose" class="btn-danger-outline">{{ t('exchanges.closeExchange') }}</button>
          </div>
        </div>

        <!-- Roles exposed by org A -->
        <section class="detail-section">
          <h4 class="section-title">{{ t('exchanges.exposedBy', { org: orgName(selected.org_a_id) }) }}</h4>
          <div v-if="!rolesForOrg(selected.org_a_id).length" class="empty-msg">{{ t('exchanges.noExposedRoles') }}</div>
          <div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:8px">
            <span v-for="r in rolesForOrg(selected.org_a_id)" :key="r.role_id" class="chip chip--role">
              {{ r.role_org_name }}:{{ r.role_name }}
              <button v-if="canManageOrg(selected.org_a_id)" @click="unexposeRole(r.role_id)" class="chip-remove" title="Remove">×</button>
            </span>
          </div>
          <div v-if="canManageOrg(selected.org_a_id)" style="display:flex;gap:8px">
            <select v-model="exposeIdA" class="select-sm">
              <option value="">{{ t('exchanges.exposeRole') }}</option>
              <option v-for="r in exposeCandidates(selected.org_a_id)" :key="r.id" :value="r.id">{{ orgName(r.org_id) }}:{{ r.name }}</option>
            </select>
            <button @click="exposeRole(exposeIdA); exposeIdA=''" :disabled="!exposeIdA" class="btn-sm btn-primary">{{ t('exchanges.expose') }}</button>
          </div>
        </section>

        <!-- Roles exposed by org B -->
        <section class="detail-section" style="border-bottom:none">
          <h4 class="section-title">{{ t('exchanges.exposedBy', { org: orgName(selected.org_b_id) }) }}</h4>
          <div v-if="!rolesForOrg(selected.org_b_id).length" class="empty-msg">{{ t('exchanges.noExposedRoles') }}</div>
          <div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:8px">
            <span v-for="r in rolesForOrg(selected.org_b_id)" :key="r.role_id" class="chip chip--role">
              {{ r.role_org_name }}:{{ r.role_name }}
              <button v-if="canManageOrg(selected.org_b_id)" @click="unexposeRole(r.role_id)" class="chip-remove" title="Remove">×</button>
            </span>
          </div>
          <div v-if="canManageOrg(selected.org_b_id)" style="display:flex;gap:8px">
            <select v-model="exposeIdB" class="select-sm">
              <option value="">{{ t('exchanges.exposeRole') }}</option>
              <option v-for="r in exposeCandidates(selected.org_b_id)" :key="r.id" :value="r.id">{{ orgName(r.org_id) }}:{{ r.name }}</option>
            </select>
            <button @click="exposeRole(exposeIdB); exposeIdB=''" :disabled="!exposeIdB" class="btn-sm btn-primary">{{ t('exchanges.expose') }}</button>
          </div>
        </section>

        <p v-if="detailErr" class="err-msg">{{ detailErr }}</p>
      </div>

      <div v-else class="card" style="padding:40px;text-align:center;color:#aaa">
        {{ t('exchanges.selectExchange') }}
      </div>
    </div>

    <!-- Create exchange modal -->
    <div v-if="showCreate" class="modal-backdrop">
      <div class="modal">
        <h3>{{ t('exchanges.createTitle') }}</h3>
        <label>{{ t('exchanges.yourOrg') }}</label>
        <select v-model="createForm.org_id" class="field">
          <option value="">{{ t('exchanges.selectOrg') }}</option>
          <option v-for="o in adminOrgs" :key="o.id" :value="o.id">{{ o.name }}</option>
        </select>
        <label>{{ t('exchanges.partnerOrg') }}</label>
        <select v-model="createForm.partner_org_id" class="field">
          <option value="">{{ t('exchanges.selectOrg') }}</option>
          <option v-for="o in partnerOrgs" :key="o.id" :value="o.id">{{ o.name }}</option>
        </select>
        <div style="display:flex;gap:8px;justify-content:flex-end">
          <button @click="showCreate=false" class="btn-cancel">{{ t('common.cancel') }}</button>
          <button @click="createExchange" :disabled="!createForm.org_id || !createForm.partner_org_id" class="btn-primary">{{ t('common.create') }}</button>
        </div>
        <p v-if="createErr" class="err-msg">{{ createErr }}</p>
      </div>
    </div>

    <!-- Close exchange confirmation modal -->
    <div v-if="showCloseConfirm" class="modal-backdrop">
      <div class="modal">
        <h3>{{ t('exchanges.closeExchange') }}</h3>
        <p v-if="impact">
          {{ t('exchanges.closeImpactInclusions', { n: impact.inclusions_removed }) }}
        </p>
        <p v-if="impact && impact.partner_exposed_roles > 0" style="color:#c00;font-size:.9em">
          {{ t('exchanges.closeImpactPartner', { n: impact.partner_exposed_roles, org: impact.partner_org_name }) }}
        </p>
        <div style="display:flex;gap:8px;justify-content:flex-end">
          <button @click="showCloseConfirm=false" class="btn-cancel">{{ t('common.cancel') }}</button>
          <button @click="doClose" class="btn-danger">{{ t('exchanges.closeExchange') }}</button>
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

const exchanges = ref([])
const orgs      = ref([])
const allRoles  = ref([])
const loading   = ref(true)
const selected  = ref(null)
const showCreate = ref(false)
const createForm = ref({ org_id: '', partner_org_id: '' })
const createErr  = ref('')
const detailErr  = ref('')
const exposeIdA  = ref('')
const exposeIdB  = ref('')
const showCloseConfirm = ref(false)
const impact     = ref(null)

function orgName(id) { return orgs.value.find(o => o.id === id)?.name ?? id }

// Build org subtree for the current user
const adminSubtreeIds = computed(() => {
  if (!auth.user) return new Set()
  if (auth.user.is_superadmin) return new Set(orgs.value.map(o => o.id))
  const ids = new Set()
  // Walk down from user's org
  const queue = [auth.user.org_id]
  while (queue.length) {
    const pid = queue.shift()
    ids.add(pid)
    for (const c of orgs.value.filter(o => o.parent_id === pid)) {
      if (!ids.has(c.id)) queue.push(c.id)
    }
  }
  return ids
})

const adminOrgs = computed(() =>
  orgs.value.filter(o => adminSubtreeIds.value.has(o.id))
)

// Partner orgs = all orgs not in admin's subtree
const partnerOrgs = computed(() =>
  orgs.value.filter(o => !adminSubtreeIds.value.has(o.id))
)

function canManageOrg(orgId) {
  return auth.isAdmin && adminSubtreeIds.value.has(orgId)
}

// Group exchanges by the partner org from the admin's perspective
const groupedExchanges = computed(() => {
  const groups = {}
  for (const ex of exchanges.value) {
    // Determine which side is "ours" and which is "partner"
    const aIsOwn = adminSubtreeIds.value.has(ex.org_a_id)
    const bIsOwn = adminSubtreeIds.value.has(ex.org_b_id)
    // partner = the side that isn't in our subtree (or both if superadmin)
    let partnerOrgId, partnerOrgName, ownOrgName
    if (aIsOwn && !bIsOwn) {
      partnerOrgId = ex.org_b_id; partnerOrgName = ex.org_b_name; ownOrgName = ex.org_a_name
    } else if (bIsOwn && !aIsOwn) {
      partnerOrgId = ex.org_a_id; partnerOrgName = ex.org_a_name; ownOrgName = ex.org_b_name
    } else {
      // Both in scope (superadmin) — use org_b as partner arbitrarily
      partnerOrgId = ex.org_b_id; partnerOrgName = ex.org_b_name; ownOrgName = ex.org_a_name
    }
    if (!groups[partnerOrgId]) {
      groups[partnerOrgId] = { partnerOrgId, partnerOrgName, exchanges: [], totalRoles: 0, open: true }
    }
    groups[partnerOrgId].exchanges.push({ ...ex, ownOrgName, partnerOrgName })
    groups[partnerOrgId].totalRoles += ex.exposed_roles.length
  }
  return Object.values(groups)
})

function rolesForOrg(orgId) {
  if (!selected.value) return []
  return selected.value.exposed_roles.filter(r => r.role_org_id === orgId)
}

function exposeCandidates(orgId) {
  if (!selected.value) return []
  const exposedIds = new Set(selected.value.exposed_roles.map(r => r.role_id))
  return allRoles.value.filter(r => r.org_id === orgId && !exposedIds.has(r.id))
}

async function load() {
  loading.value = true
  try {
    const [e, o, r] = await Promise.all([
      api.get('/exchanges/'),
      api.get('/orgs/'),
      api.get('/roles/'),
    ])
    exchanges.value = e.data
    orgs.value = o.data
    allRoles.value = r.data
  } finally {
    loading.value = false
  }
}

function selectExchange(ex) {
  selected.value = ex
  detailErr.value = ''
  exposeIdA.value = exposeIdB.value = ''
}

async function reloadSelected() {
  if (!selected.value) return
  try {
    const res = await api.get(`/exchanges/${selected.value.id}`)
    selected.value = res.data
    // Also refresh the list
    const e = await api.get('/exchanges/')
    exchanges.value = e.data
  } catch { /* ignore */ }
}

async function createExchange() {
  createErr.value = ''
  try {
    const res = await api.post('/exchanges/', createForm.value)
    showCreate.value = false
    createForm.value = { org_id: '', partner_org_id: '' }
    await load()
    selectExchange(res.data)
  } catch (e) { createErr.value = e.response?.data?.detail ?? 'Error' }
}

async function confirmClose() {
  try {
    const res = await api.get(`/exchanges/${selected.value.id}/impact`)
    impact.value = res.data
    showCloseConfirm.value = true
  } catch (e) { detailErr.value = e.response?.data?.detail ?? 'Error' }
}

async function doClose() {
  try {
    await api.delete(`/exchanges/${selected.value.id}`)
    showCloseConfirm.value = false
    selected.value = null
    await load()
  } catch (e) { detailErr.value = e.response?.data?.detail ?? 'Error' }
}

async function exposeRole(roleId) {
  if (!roleId) return
  detailErr.value = ''
  try {
    await api.post(`/exchanges/${selected.value.id}/roles`, { role_id: roleId })
    await reloadSelected()
  } catch (e) { detailErr.value = e.response?.data?.detail ?? 'Error' }
}

async function unexposeRole(roleId) {
  detailErr.value = ''
  try {
    await api.delete(`/exchanges/${selected.value.id}/roles/${roleId}`)
    await reloadSelected()
  } catch (e) { detailErr.value = e.response?.data?.detail ?? 'Error' }
}

onMounted(load)
</script>

<style scoped>
.card { background:#fff; border-radius:8px; box-shadow:0 1px 4px rgba(0,0,0,.1); }

.exchange-item {
  padding:6px 10px; border-radius:4px; cursor:pointer; margin-bottom:2px;
  border-left:3px solid transparent; display:flex; flex-direction:column; gap:2px;
}
.exchange-item:hover { background:#f5f7fa; }
.exchange-item--active { border-left-color:#1e3a5f; background:#f0f4f8; }

.detail-section { margin-bottom:20px; padding-bottom:20px; border-bottom:1px solid #eee; }
.section-title { margin:0 0 10px; font-size:.9em; text-transform:uppercase; letter-spacing:.04em; color:#555; }
.empty-msg { color:#aaa; font-size:.9em; margin-bottom:6px; }

.chip { display:inline-flex; align-items:center; gap:4px; padding:3px 8px; border-radius:12px; font-size:.82em; }
.chip--role { background:#e3f2fd; color:#1565c0; }
.chip-remove { background:none; border:none; cursor:pointer; font-size:1.1em; line-height:1; padding:0 1px; opacity:.6; }
.chip-remove:hover { opacity:1; }

.select-sm { padding:5px 8px; border:1px solid #ccc; border-radius:4px; flex:1; font-size:.9em; }
.field { display:block; width:100%; padding:7px; margin:4px 0 14px; border:1px solid #ccc; border-radius:4px; }
.err-msg { color:#c00; font-size:.85em; margin-top:6px; }

.btn-primary { padding:6px 14px; background:#1e3a5f; color:#fff; border:none; border-radius:4px; cursor:pointer; }
.btn-cancel { padding:6px 14px; border:1px solid #ccc; border-radius:4px; cursor:pointer; background:#fff; }
.btn-danger-outline { padding:4px 10px; border:1px solid #c00; border-radius:4px; cursor:pointer; color:#c00; background:#fff; font-size:.85em; }
.btn-danger { padding:6px 14px; background:#c00; color:#fff; border:none; border-radius:4px; cursor:pointer; }
.btn-sm { padding:5px 12px; border:none; border-radius:4px; cursor:pointer; font-size:.9em; }
.btn-sm:disabled { opacity:.4; cursor:default; }

.help-link {
  display:inline-flex; align-items:center; justify-content:center;
  width:18px; height:18px; border-radius:50%; background:#1e3a5f; color:#fff;
  font-size:.75em; font-weight:700; text-decoration:none; flex-shrink:0;
}

.modal-backdrop { position:fixed; inset:0; background:rgba(0,0,0,.4); display:flex; align-items:center; justify-content:center; z-index:100; }
.modal { background:#fff; border-radius:8px; padding:24px; width:420px; max-width:95vw; }
.modal h3 { margin:0 0 16px; }
</style>
