<template>
  <div>
    <h2 style="margin-bottom:4px">Org Interactions</h2>
    <p style="color:#666;font-size:.9em;margin-bottom:20px">
      Cross-org role relationships within your admin scope. Parent/child orgs are excluded — only lateral interactions are shown.
    </p>

    <div v-if="loading" style="color:#888;padding:20px">Loading…</div>
    <div v-else-if="!tree.length" style="color:#888">No orgs in scope.</div>

    <div v-else>
      <OrgInteractionNode
        v-for="node in roots"
        :key="node.org_id"
        :node="node"
        :all-nodes="tree"
        :depth="0"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, defineComponent, h } from 'vue'
import api from '../stores/api.js'

const tree    = ref([])
const loading = ref(true)

const roots = computed(() => tree.value.filter(n => !n.parent_id || !tree.value.find(x => x.org_id === n.parent_id)))

async function load() {
  try {
    const res = await api.get('/interactions/')
    tree.value = res.data
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<script>
import { defineComponent, h, ref } from 'vue'

const RelationBadge = defineComponent({
  props: ['relation'],
  setup(props) {
    return () => h('span', {
      style: `display:inline-block;padding:1px 7px;border-radius:10px;font-size:.75em;font-weight:600;
              background:${props.relation === 'includes' ? '#e3f2fd' : '#fce4ec'};
              color:${props.relation === 'includes' ? '#1565c0' : '#c62828'}`,
    }, props.relation === 'includes' ? '⊃ includes' : '⊂ included by')
  },
})

const ForeignOrgPanel = defineComponent({
  name: 'ForeignOrgPanel',
  props: ['interaction'],
  setup(props) {
    const open = ref(false)
    return () => {
      const { foreign_org_name, roles } = props.interaction
      return h('div', { style: 'margin-bottom:8px' }, [
        // Header row — click to expand
        h('div', {
          onClick: () => { open.value = !open.value },
          style: `display:flex;align-items:center;gap:8px;padding:8px 12px;
                  background:#f8f9fb;border-radius:6px;cursor:pointer;
                  border-left:3px solid #1e3a5f;user-select:none`,
        }, [
          h('span', { style: 'font-size:.85em;opacity:.6' }, open.value ? '▾' : '▸'),
          h('strong', { style: 'flex:1' }, foreign_org_name),
          h('span', {
            style: 'font-size:.78em;background:#e0e0e0;color:#444;padding:1px 7px;border-radius:10px',
          }, `${roles.length} link${roles.length !== 1 ? 's' : ''}`),
        ]),
        // Role links table (shown when expanded)
        open.value
          ? h('div', { style: 'margin-top:4px;margin-left:12px' },
              roles.map(role =>
                h('div', {
                  key: role.this_role_id + role.foreign_role_id,
                  style: `display:flex;align-items:center;gap:8px;padding:5px 10px;
                          border-bottom:1px solid #f0f0f0;font-size:.85em`,
                }, [
                  h('span', { style: 'color:#333;font-weight:500' }, role.this_role_name),
                  h(RelationBadge, { relation: role.relation }),
                  h('span', { style: 'color:#555' }, role.foreign_role_name),
                  h('span', { style: 'color:#aaa;font-size:.8em;margin-left:4px' }, `(${foreign_org_name})`),
                ])
              )
            )
          : null,
      ])
    }
  },
})

const OrgInteractionNode = defineComponent({
  name: 'OrgInteractionNode',
  props: ['node', 'allNodes', 'depth'],
  setup(props) {
    const open = ref(true)
    return () => {
      const children = props.allNodes.filter(n => n.parent_id === props.node.org_id)
      const { org_id, org_name, interactions } = props.node

      return h('div', { style: `margin-left:${props.depth * 22}px;margin-bottom:10px` }, [
        // Org header
        h('div', {
          style: `display:flex;align-items:center;gap:8px;padding:10px 14px;
                  background:#fff;border-radius:8px;box-shadow:0 1px 4px rgba(0,0,0,.08);
                  border-left:4px solid ${interactions.length ? '#1e3a5f' : '#ddd'}`,
        }, [
          h('span', {
            onClick: () => { open.value = !open.value },
            style: 'cursor:pointer;opacity:.5;font-size:.85em;user-select:none',
            title: 'Toggle children',
          }, children.length ? (open.value ? '▾' : '▸') : ''),
          h('span', { style: 'font-weight:600;flex:1' }, org_name),
          interactions.length
            ? h('span', {
                style: 'font-size:.78em;background:#1e3a5f;color:#fff;padding:2px 8px;border-radius:10px',
              }, `${interactions.length} foreign org${interactions.length !== 1 ? 's' : ''}`)
            : h('span', { style: 'font-size:.78em;color:#bbb' }, 'no cross-org interactions'),
        ]),

        // Interaction panels
        interactions.length && open.value
          ? h('div', { style: 'margin:6px 0 4px 18px' },
              interactions.map(interaction =>
                h(ForeignOrgPanel, { key: interaction.foreign_org_id, interaction })
              )
            )
          : null,

        // Child orgs
        open.value
          ? children.map(child =>
              h(OrgInteractionNode, {
                key: child.org_id,
                node: child,
                allNodes: props.allNodes,
                depth: props.depth + 1,
              })
            )
          : null,
      ])
    }
  },
})

export default { components: { OrgInteractionNode } }
</script>
