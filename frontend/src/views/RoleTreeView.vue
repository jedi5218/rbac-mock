<template>
  <div>
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:16px">
      <h2 style="margin:0">{{ t('roleTree.title') }}</h2>
      <router-link to="/wiki/role-tree" class="help-link" :title="t('common.help')">?</router-link>
    </div>

    <!-- User picker: admins choose; regular users see only themselves -->
    <div style="background:#fff;border-radius:8px;padding:20px;box-shadow:0 1px 4px rgba(0,0,0,.1);margin-bottom:20px">
      <div style="display:flex;gap:12px;align-items:flex-end">
        <div style="flex:1">
          <label style="font-weight:500;display:block;margin-bottom:6px">{{ t('roleTree.selectUser') }}</label>
          <select v-if="auth.isAdmin" v-model="selectedUserId" style="width:100%;padding:8px;border:1px solid #ccc;border-radius:4px">
            <option value="">{{ t('roleTree.chooseUser') }}</option>
            <option v-for="u in users" :key="u.id" :value="u.id">{{ u.username }} ({{ orgName(u.org_id) }})</option>
          </select>
          <div v-else style="padding:8px;border:1px solid #eee;border-radius:4px;background:#f8f9fb;color:#555">
            {{ auth.user?.username }}
          </div>
        </div>
        <button v-if="auth.isAdmin" @click="fetchTree" :disabled="!selectedUserId || loading"
          style="padding:8px 18px;background:#1e3a5f;color:#fff;border:none;border-radius:4px;cursor:pointer">
          {{ t('roleTree.viewBtn') }}
        </button>
      </div>
    </div>

    <div v-if="loading" style="color:#888;padding:20px">{{ t('common.loading') }}</div>

    <div v-else-if="tree" style="background:#fff;border-radius:8px;padding:20px;box-shadow:0 1px 4px rgba(0,0,0,.1)">
      <div style="display:flex;align-items:baseline;gap:8px;margin-bottom:16px">
        <h3 style="margin:0">{{ tree.username }}</h3>
        <span style="font-size:.85em;color:#888">{{ orgName(targetOrgId) }}</span>
      </div>
      <div v-if="!tree.roles.length" style="color:#888;padding:8px 0">{{ t('roleTree.noRoles') }}</div>
      <div v-else>
        <RoleTreeNode
          v-for="(node, idx) in tree.roles"
          :key="node.id + '-root-' + idx"
          :node="node"
          :depth="0"
          :is-direct="true"
          :hierarchy-org-ids="hierarchyOrgIds"
          :org-name-fn="orgName"
        />
      </div>
    </div>

    <p v-if="err" style="color:red;margin-top:12px">{{ err }}</p>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '../stores/auth.js'
import api from '../stores/api.js'

const { t } = useI18n()
const auth = useAuthStore()

const users   = ref([])
const orgs    = ref([])
const tree    = ref(null)
const loading = ref(false)
const err     = ref('')
const selectedUserId = ref('')

function orgName(id) { return orgs.value.find(o => o.id === id)?.name || id }

const targetOrgId = computed(() =>
  users.value.find(u => u.id === selectedUserId.value)?.org_id || auth.user?.org_id || ''
)

// Org IDs in the viewing admin's ancestor + descendant chain (null = superadmin)
const hierarchyOrgIds = computed(() => {
  if (!auth.user || auth.user.is_superadmin) return null
  const all = orgs.value
  const inScope = new Set()
  let cur = all.find(o => o.id === auth.user.org_id)
  while (cur) {
    inScope.add(cur.id)
    cur = cur.parent_id ? all.find(o => o.id === cur.parent_id) : null
  }
  const queue = [auth.user.org_id]
  while (queue.length) {
    const pid = queue.shift()
    for (const c of all.filter(o => o.parent_id === pid)) {
      if (!inScope.has(c.id)) { inScope.add(c.id); queue.push(c.id) }
    }
  }
  return inScope
})

async function load() {
  const [u, o] = await Promise.all([api.get('/users/'), api.get('/orgs/')])
  users.value = u.data
  orgs.value  = o.data
  // For regular users, auto-select and fetch their own tree
  if (!auth.isAdmin) {
    selectedUserId.value = auth.user.id
    await fetchTree()
  }
}

async function fetchTree() {
  if (!selectedUserId.value) return
  err.value = ''
  tree.value = null
  loading.value = true
  try {
    const res = await api.get(`/users/${selectedUserId.value}/role-tree`)
    tree.value = res.data
  } catch (e) {
    err.value = e.response?.data?.detail || 'Error'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<script>
import { defineComponent, h, ref } from 'vue'

const RoleTreeNode = defineComponent({
  name: 'RoleTreeNode',
  props: ['node', 'depth', 'isDirect', 'hierarchyOrgIds', 'orgNameFn'],
  setup(props) {
    const open = ref(true)

    return () => {
      const { node, depth, isDirect, hierarchyOrgIds, orgNameFn } = props
      const hasChildren = node.included.length > 0
      const isForeign = hierarchyOrgIds !== null && !hierarchyOrgIds.has(node.org_id)

      const row = h('div', {
        style: `display:flex;align-items:center;gap:6px;padding:5px 2px;
                border-left:${depth === 0 ? '3px solid #1e3a5f' : '3px solid transparent'};
                padding-left:${depth === 0 ? '10px' : '2px'}`,
      }, [
        // Expand toggle or leaf bullet
        hasChildren && !node.is_cycle
          ? h('span', {
              onClick: () => { open.value = !open.value },
              style: 'cursor:pointer;color:#888;width:14px;text-align:center;user-select:none;flex-shrink:0',
            }, open.value ? '▾' : '▸')
          : h('span', { style: 'width:14px;text-align:center;color:#ccc;flex-shrink:0' }, '•'),

        // Role name
        h('span', {
          style: `font-weight:${isDirect ? '600' : '400'};${node.is_propagation_blocked ? 'opacity:.5;text-decoration:line-through' : ''}`,
        }, node.name),

        // Org name
        h('span', { style: 'font-size:.78em;color:#888' }, orgNameFn(node.org_id)),

        // Badges
        isDirect
          ? h('span', { class: 'rt-badge rt-badge--direct' }, 'direct')
          : null,
        node.is_org_role
          ? h('span', { class: 'rt-badge rt-badge--org' }, 'org')
          : null,
        isForeign
          ? h('span', { class: 'rt-badge rt-badge--foreign' }, 'foreign')
          : null,
        node.is_propagation_blocked
          ? h('span', { class: 'rt-badge rt-badge--blocked' }, 'blocked')
          : null,
      ])

      const children = hasChildren && open.value && !node.is_cycle
        ? node.included.map((child, idx) =>
            h(RoleTreeNode, {
              key: `${child.id}-${depth + 1}-${idx}`,
              node: child,
              depth: depth + 1,
              isDirect: false,
              hierarchyOrgIds,
              orgNameFn,
            })
          )
        : []

      return h('div', { style: `margin-left:${depth === 0 ? 0 : 20}px` }, [row, ...children])
    }
  },
})

export default { components: { RoleTreeNode } }
</script>

<style scoped>
.help-link {
  display: inline-flex; align-items: center; justify-content: center;
  width: 18px; height: 18px; border-radius: 50%; background: #1e3a5f; color: #fff;
  font-size: .75em; font-weight: 700; text-decoration: none; flex-shrink: 0;
}
.rt-badge {
  padding: 1px 6px; border-radius: 8px; font-size: .7em; font-weight: 600;
  letter-spacing: .02em; flex-shrink: 0;
}
.rt-badge--direct  { background: #e8f5e9; color: #2e7d32; }
.rt-badge--org     { background: #fff3e0; color: #e65100; }
.rt-badge--foreign { background: #fce4ec; color: #880e4f; }
.rt-badge--blocked { background: #e0e0e0; color: #757575; text-decoration: line-through; }
</style>
