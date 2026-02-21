# Role Tree

The **Role Tree** view visualises the full role inclusion hierarchy for a selected user.

## Access

- **Regular users** see their own role tree automatically.
- **Org admins** can select any user within their org subtree.
- **Superadmins** can select any user in the system.

## Reading the tree

Each node in the tree represents a role. Root-level nodes are roles **directly assigned** to the user. Child nodes are roles **included** (inherited) by their parent role.

- **▾ / ▸** — click to expand or collapse a branch
- **•** — leaf node (no inclusions)
- `pub` badge — role is public (usable cross-org as a parent)
- `org` badge — auto-managed org-member role
- `foreign` badge — role belongs to an org outside your ancestor/descendant chain

## Cycle handling

Role inclusions can form cycles (DAG enforcement is disabled). When a cycle is detected in a branch, that node is shown as a leaf to prevent infinite expansion.

## Relationship to Resolve

The Role Tree shows **structure** (which roles include which). The [Resolve](resolve) view shows **outcome** (the effective resource permissions after merging the whole tree).
