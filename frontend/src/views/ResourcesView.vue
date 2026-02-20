<template>
  <div>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
      <h2>Resources</h2>
      <button v-if="auth.isAdmin" @click="showCreate=true" style="padding:6px 14px;background:#1e3a5f;color:#fff;border:none;border-radius:4px;cursor:pointer">+ New Resource</button>
    </div>

    <table style="width:100%;background:#fff;border-radius:8px;border-collapse:collapse;box-shadow:0 1px 4px rgba(0,0,0,.1)">
      <thead>
        <tr style="background:#f0f4f8">
          <th style="padding:10px;text-align:left">Name</th>
          <th style="padding:10px;text-align:left">Type</th>
          <th style="padding:10px;text-align:left">Org</th>
          <th v-if="auth.isAdmin" style="padding:10px;text-align:left">Actions</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="r in resources" :key="r.id" style="border-top:1px solid #eee">
          <td style="padding:10px">{{ r.name }}</td>
          <td style="padding:10px">
            <span :style="`padding:2px 8px;border-radius:10px;font-size:.85em;background:${r.resource_type==='document'?'#e3f2fd':'#fce4ec'}`">{{ r.resource_type }}</span>
          </td>
          <td style="padding:10px">{{ orgName(r.org_id) }}</td>
          <td v-if="auth.isAdmin" style="padding:10px">
            <button @click="deleteResource(r)" style="padding:2px 8px;font-size:.85em;cursor:pointer;border:1px solid #e55;border-radius:3px;background:#fff;color:#e55">Delete</button>
          </td>
        </tr>
        <tr v-if="!resources.length">
          <td :colspan="auth.isAdmin ? 4 : 3" style="padding:16px;text-align:center;color:#888">No resources</td>
        </tr>
      </tbody>
    </table>

    <!-- Create modal -->
    <div v-if="showCreate" class="modal-backdrop">
      <div class="modal">
        <h3>Create Resource</h3>
        <label>Name</label>
        <input v-model="form.name" class="field" />
        <label>Type</label>
        <select v-model="form.resource_type" class="field">
          <option value="document">document</option>
          <option value="video">video</option>
        </select>
        <label>Org</label>
        <select v-model="form.org_id" class="field">
          <option v-for="o in orgs" :key="o.id" :value="o.id">{{ o.name }}</option>
        </select>
        <div style="display:flex;gap:8px;justify-content:flex-end">
          <button @click="showCreate=false" class="btn-cancel">Cancel</button>
          <button @click="createResource" class="btn-primary">Create</button>
        </div>
        <p v-if="err" style="color:red;margin-top:8px">{{ err }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useAuthStore } from '../stores/auth.js'
import api from '../stores/api.js'

const auth = useAuthStore()
const resources = ref([])
const orgs = ref([])
const showCreate = ref(false)
const form = ref({ name: '', resource_type: 'document', org_id: '' })
const err = ref('')

function orgName(id) { return orgs.value.find(o => o.id === id)?.name || id }

async function load() {
  const [r, o] = await Promise.all([api.get('/resources/'), api.get('/orgs/')])
  resources.value = r.data
  orgs.value = o.data
  if (!form.value.org_id && o.data.length) form.value.org_id = o.data[0].id
}

async function createResource() {
  err.value = ''
  try {
    await api.post('/resources/', form.value)
    showCreate.value = false
    await load()
  } catch (e) { err.value = e.response?.data?.detail || 'Error' }
}

async function deleteResource(r) {
  if (!confirm(`Delete "${r.name}"?`)) return
  try {
    await api.delete(`/resources/${r.id}`)
    await load()
  } catch (e) { alert(e.response?.data?.detail || 'Error') }
}

onMounted(load)
</script>

<style scoped>
.modal-backdrop { position:fixed;inset:0;background:rgba(0,0,0,.4);display:flex;align-items:center;justify-content:center;z-index:100 }
.modal { background:#fff;border-radius:8px;padding:24px;width:400px;max-width:95vw }
.modal h3 { margin-bottom:16px }
.field { display:block;width:100%;padding:6px;margin:4px 0 12px;border:1px solid #ccc;border-radius:4px }
.btn-cancel { padding:6px 14px;border:1px solid #ccc;border-radius:4px;cursor:pointer;background:#fff }
.btn-primary { padding:6px 14px;background:#1e3a5f;color:#fff;border:none;border-radius:4px;cursor:pointer }
</style>
