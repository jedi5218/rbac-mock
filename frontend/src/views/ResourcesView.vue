<template>
  <div>
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:16px">
      <h2 style="margin:0">{{ t('resources.title') }}</h2>
      <router-link to="/wiki/resources" class="help-link" :title="t('common.help')">?</router-link>
    </div>

    <!-- Org tree with resources -->
    <div style="background:#fff;border-radius:8px;box-shadow:0 1px 4px rgba(0,0,0,.1);padding:12px">
      <div v-if="!orgs.length" style="color:#888;padding:8px;font-size:.9em">{{ t('resources.noResources') }}</div>
      <template v-else>
        <div v-for="root in roots" :key="root.id">
          <OrgResourceNode
            :org="root"
            :depth="0"
            :children-of="childrenOf"
            :resources-for-org="resourcesForOrg"
            :collapsed-orgs="collapsedOrgs"
            :toggle-org="toggleOrg"
            :auth="auth"
            :t="t"
            :open-create="openCreateForOrg"
            :open-edit="openEdit"
            :delete-resource="deleteResource"
          />
        </div>
      </template>
    </div>

    <!-- Create / Edit modal -->
    <div v-if="showModal" class="modal-backdrop">
      <div class="modal">
        <h3>{{ editTarget ? t('resources.editTitle') : t('resources.createTitle') }}</h3>

        <label>{{ t('common.name') }}</label>
        <input v-model="form.name" class="field" />

        <label>{{ t('common.description') }}</label>
        <textarea v-model="form.description" rows="2" class="field" style="resize:vertical;font-family:inherit" />

        <label>{{ t('common.type') }}</label>
        <select v-model="form.resource_type" class="field" :disabled="!!editTarget">
          <option value="document">document</option>
          <option value="video">video</option>
        </select>

        <label>{{ t('common.org') }}</label>
        <input :value="orgName(form.org_id)" class="field" disabled />

        <!-- Role permissions for this resource -->
        <div v-if="orgRoles.length" style="margin-top:8px;margin-bottom:14px">
          <div style="font-size:.85em;font-weight:600;color:#555;text-transform:uppercase;letter-spacing:.04em;margin-bottom:8px">{{ t('resources.rolePermsTitle') }}</div>
          <div class="perm-legend">{{ t('resources.rolePermsHint') }}</div>
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
        <div v-else style="font-size:.85em;color:#aaa;margin-bottom:14px">{{ t('resources.noRoles') }}</div>

        <p v-if="err" class="err-msg">{{ err }}</p>
        <div style="display:flex;gap:8px;justify-content:flex-end">
          <button @click="showModal=false" class="btn-cancel">{{ t('common.cancel') }}</button>
          <button @click="saveModal" class="btn-primary">{{ editTarget ? t('common.save') : t('common.create') }}</button>
        </div>
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
const resources = ref([])
const orgs      = ref([])
const allRoles  = ref([])

const showModal  = ref(false)
const editTarget = ref(null)
const form       = ref({ name: '', description: '', resource_type: 'document', org_id: '' })
const resPerms   = ref({})
const origPerms  = ref({})
const err        = ref('')

const BITS = {
  document: [[1, 'read'], [2, 'write']],
  video:    [[1, 'view'], [2, 'comment'], [4, 'stream']],
}
function bitsFor(type) { return BITS[type] ?? [] }

function orgName(id) { return orgs.value.find(o => o.id === id)?.name ?? id }

// ── Org tree helpers ──────────────────────────────────────────────────────
const collapsedOrgs = ref(new Set())
const roots = computed(() => orgs.value.filter(o => !orgs.value.some(p => p.id === o.parent_id)))
function childrenOf(orgId) { return orgs.value.filter(o => o.parent_id === orgId) }
function toggleOrg(orgId) {
  const s = new Set(collapsedOrgs.value)
  s.has(orgId) ? s.delete(orgId) : s.add(orgId)
  collapsedOrgs.value = s
}
function resourcesForOrg(orgId) { return resources.value.filter(r => r.org_id === orgId) }

const orgRoles = computed(() =>
  allRoles.value.filter(r => r.org_id === form.value.org_id && !r.is_org_role)
)

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
}

function openCreateForOrg(orgId) {
  editTarget.value = null
  form.value = { name: '', description: '', resource_type: 'document', org_id: orgId }
  resPerms.value = {}
  origPerms.value = {}
  err.value = ''
  showModal.value = true
}

async function openEdit(resource) {
  editTarget.value = resource
  form.value = { name: resource.name, description: resource.description || '', resource_type: resource.resource_type, org_id: resource.org_id }
  err.value = ''
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
      await api.put(`/resources/${editTarget.value.id}`, { name: form.value.name, description: form.value.description || null })
      resourceId = editTarget.value.id
    } else {
      const r = await api.post('/resources/', form.value)
      resourceId = r.data.id
    }
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

<script>
import { defineComponent, h } from 'vue'

const OrgResourceNode = defineComponent({
  name: 'OrgResourceNode',
  props: ['org', 'depth', 'childrenOf', 'resourcesForOrg', 'collapsedOrgs', 'toggleOrg', 'auth', 't', 'openCreate', 'openEdit', 'deleteResource'],
  setup(props) {
    return () => {
      const { org, depth, childrenOf, resourcesForOrg, collapsedOrgs, toggleOrg, auth, t, openCreate, openEdit, deleteResource } = props
      const children = childrenOf(org.id)
      const orgRes = resourcesForOrg(org.id)
      const isCollapsed = collapsedOrgs.has(org.id)
      const hasContent = children.length > 0 || orgRes.length > 0

      const header = h('div', {
        style: `display:flex;align-items:center;gap:8px;padding:8px 12px;background:#f8f9fb;border-left:3px solid #1e3a5f;border-radius:4px;margin-bottom:2px${hasContent ? ';cursor:pointer' : ''}`,
        onClick: () => hasContent && toggleOrg(org.id),
      }, [
        h('span', { style: 'color:#888;width:14px;text-align:center;user-select:none;flex-shrink:0' },
          hasContent ? (isCollapsed ? '▸' : '▾') : ''),
        h('span', { style: 'font-weight:600;flex:1;color:#1e3a5f' }, org.name),
        auth.isAdmin
          ? h('button', {
              style: 'width:22px;height:22px;border-radius:50%;background:#1e3a5f;color:#fff;border:none;cursor:pointer;font-size:1em;line-height:1;display:flex;align-items:center;justify-content:center;flex-shrink:0',
              onClick: (e) => { e.stopPropagation(); openCreate(org.id) },
            }, '+')
          : null,
      ])

      const items = isCollapsed ? [] : [
        ...orgRes.map(r =>
          h('div', {
            key: r.id,
            style: `display:flex;align-items:center;gap:8px;padding:6px 10px 6px 28px;margin-bottom:1px;border-bottom:1px solid #f5f5f5${auth.isAdmin ? ';cursor:pointer' : ''}`,
            onClick: () => auth.isAdmin && openEdit(r),
          }, [
            h('span', { style: 'font-weight:500;flex:1' }, [
              r.name,
              r.description ? h('span', { style: 'display:block;font-size:.8em;color:#888;font-weight:normal;margin-top:1px;white-space:pre-wrap' }, r.description) : null,
            ]),
            h('span', {
              style: r.resource_type === 'document'
                ? 'padding:2px 8px;border-radius:10px;font-size:.8em;flex-shrink:0;background:#e3f2fd;color:#1565c0'
                : 'padding:2px 8px;border-radius:10px;font-size:.8em;flex-shrink:0;background:#fce4ec;color:#c62828',
            }, r.resource_type),
            auth.isAdmin
              ? h('button', {
                  style: 'padding:2px 8px;font-size:.8em;cursor:pointer;border:1px solid #e55;border-radius:3px;background:#fff;color:#e55;flex-shrink:0',
                  onClick: (e) => { e.stopPropagation(); deleteResource(r) },
                }, t('common.delete'))
              : null,
          ])
        ),
        ...children.map(child =>
          h(OrgResourceNode, {
            key: child.id,
            org: child,
            depth: depth + 1,
            childrenOf, resourcesForOrg, collapsedOrgs, toggleOrg, auth, t, openCreate, openEdit, deleteResource,
          })
        ),
      ]

      return h('div', { style: `margin-left:${depth === 0 ? 0 : 20}px;margin-bottom:4px` }, [header, ...items])
    }
  },
})

export default { components: { OrgResourceNode } }
</script>

<style scoped>
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
.help-link {
  display: inline-flex; align-items: center; justify-content: center;
  width: 18px; height: 18px; border-radius: 50%; background: #1e3a5f; color: #fff;
  font-size: .75em; font-weight: 700; text-decoration: none; flex-shrink: 0;
}
</style>
