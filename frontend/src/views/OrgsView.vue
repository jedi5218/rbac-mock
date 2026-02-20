<template>
  <div>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
      <h2>Organizations</h2>
      <button v-if="auth.isSuperadmin" @click="showCreate=true" style="padding:6px 14px;background:#1e3a5f;color:#fff;border:none;border-radius:4px;cursor:pointer">+ New Org</button>
    </div>

    <!-- Tree display -->
    <div style="background:#fff;border-radius:8px;padding:16px;box-shadow:0 1px 4px rgba(0,0,0,.1)">
      <OrgNode v-for="o in roots" :key="o.id" :org="o" :all-orgs="orgs" :depth="0" @edit="startEdit" @delete="deleteOrg" :is-superadmin="auth.isSuperadmin" />
      <p v-if="!orgs.length" style="color:#888">No organizations</p>
    </div>

    <!-- Create modal -->
    <div v-if="showCreate" class="modal-backdrop">
      <div class="modal">
        <h3>Create Organization</h3>
        <label>Name</label>
        <input v-model="form.name" style="display:block;width:100%;padding:6px;margin:4px 0 12px;border:1px solid #ccc;border-radius:4px" />
        <label>Parent Org (optional)</label>
        <select v-model="form.parent_id" style="display:block;width:100%;padding:6px;margin:4px 0 12px;border:1px solid #ccc;border-radius:4px">
          <option value="">— none (root) —</option>
          <option v-for="o in orgs" :key="o.id" :value="o.id">{{ o.name }}</option>
        </select>
        <div style="display:flex;gap:8px;justify-content:flex-end">
          <button @click="showCreate=false" style="padding:6px 14px;border:1px solid #ccc;border-radius:4px;cursor:pointer;background:#fff">Cancel</button>
          <button @click="createOrg" style="padding:6px 14px;background:#1e3a5f;color:#fff;border:none;border-radius:4px;cursor:pointer">Create</button>
        </div>
        <p v-if="err" style="color:red;margin-top:8px">{{ err }}</p>
      </div>
    </div>

    <!-- Edit modal -->
    <div v-if="editTarget" class="modal-backdrop">
      <div class="modal">
        <h3>Edit Organization</h3>
        <label>Name</label>
        <input v-model="editForm.name" style="display:block;width:100%;padding:6px;margin:4px 0 12px;border:1px solid #ccc;border-radius:4px" />
        <label>Parent Org (optional)</label>
        <select v-model="editForm.parent_id" style="display:block;width:100%;padding:6px;margin:4px 0 12px;border:1px solid #ccc;border-radius:4px">
          <option value="">— none (root) —</option>
          <option v-for="o in orgs.filter(x => x.id !== editTarget.id)" :key="o.id" :value="o.id">{{ o.name }}</option>
        </select>
        <div style="display:flex;gap:8px;justify-content:flex-end">
          <button @click="editTarget=null" style="padding:6px 14px;border:1px solid #ccc;border-radius:4px;cursor:pointer;background:#fff">Cancel</button>
          <button @click="saveEdit" style="padding:6px 14px;background:#1e3a5f;color:#fff;border:none;border-radius:4px;cursor:pointer">Save</button>
        </div>
        <p v-if="err" style="color:red;margin-top:8px">{{ err }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useAuthStore } from '../stores/auth.js'
import api from '../stores/api.js'

const auth = useAuthStore()
const orgs = ref([])
const showCreate = ref(false)
const editTarget = ref(null)
const form = ref({ name: '', parent_id: '' })
const editForm = ref({ name: '', parent_id: '' })
const err = ref('')

const roots = computed(() => orgs.value.filter(o => !o.parent_id))

async function load() {
  const res = await api.get('/orgs/')
  orgs.value = res.data
}

async function createOrg() {
  err.value = ''
  try {
    await api.post('/orgs/', { name: form.value.name, parent_id: form.value.parent_id || null })
    showCreate.value = false
    form.value = { name: '', parent_id: '' }
    await load()
  } catch (e) { err.value = e.response?.data?.detail || 'Error' }
}

function startEdit(org) {
  editTarget.value = org
  editForm.value = { name: org.name, parent_id: org.parent_id || '' }
}

async function saveEdit() {
  err.value = ''
  try {
    await api.put(`/orgs/${editTarget.value.id}`, {
      name: editForm.value.name,
      parent_id: editForm.value.parent_id || null,
    })
    editTarget.value = null
    await load()
  } catch (e) { err.value = e.response?.data?.detail || 'Error' }
}

async function deleteOrg(org) {
  if (!confirm(`Delete "${org.name}"?`)) return
  try {
    await api.delete(`/orgs/${org.id}`)
    await load()
  } catch (e) { alert(e.response?.data?.detail || 'Error') }
}

onMounted(load)
</script>

<script>
import { defineComponent, h } from 'vue'

// Recursive tree node component
const OrgNode = defineComponent({
  name: 'OrgNode',
  props: ['org', 'allOrgs', 'depth', 'isSuperadmin'],
  emits: ['edit', 'delete'],
  setup(props, { emit }) {
    return () => {
      const children = props.allOrgs.filter(o => o.parent_id === props.org.id)
      return h('div', { style: `margin-left:${props.depth * 20}px;margin-bottom:6px` }, [
        h('div', {
          style: 'display:flex;align-items:center;gap:8px;padding:8px 12px;background:#f8f9fb;border-left:3px solid #1e3a5f;border-radius:4px',
        }, [
          h('span', { style: 'flex:1' }, props.org.name),
          props.isSuperadmin ? h('button', {
            onClick: () => emit('edit', props.org),
            style: 'padding:2px 8px;font-size:.8em;cursor:pointer;border:1px solid #ccc;border-radius:3px;background:#fff',
          }, 'Edit') : null,
          props.isSuperadmin ? h('button', {
            onClick: () => emit('delete', props.org),
            style: 'padding:2px 8px;font-size:.8em;cursor:pointer;border:1px solid #e55;border-radius:3px;background:#fff;color:#e55',
          }, 'Delete') : null,
        ]),
        ...children.map(c => h(OrgNode, {
          org: c, allOrgs: props.allOrgs, depth: props.depth + 1,
          isSuperadmin: props.isSuperadmin,
          onEdit: (o) => emit('edit', o),
          onDelete: (o) => emit('delete', o),
        })),
      ])
    }
  },
})
export default { components: { OrgNode } }
</script>

<style scoped>
.modal-backdrop {
  position: fixed; inset: 0; background: rgba(0,0,0,.4);
  display: flex; align-items: center; justify-content: center; z-index: 100;
}
.modal {
  background: #fff; border-radius: 8px; padding: 24px; width: 400px; max-width: 95vw;
}
.modal h3 { margin-bottom: 16px; }
</style>
