# Foreign Propagation Algorithm

When roles cross org boundaries through [exchanges](/wiki/exchanges), a propagation limit prevents unintended transitive permission leaks. This page walks through the algorithm and its rationale.

## The Problem

Without propagation limits, cross-org role sharing is transitive. If org A shares a role with org B, and org B shares a role with org C, then A's permissions could leak to C through B — even though A and C have no agreement.

Simply blocking all foreign role inheritance is too restrictive: it would prevent a parent org from granting a foreign role's permissions to its child orgs, which is a natural administrative pattern.

## Vertical Line

The key concept is the **vertical line** of an org. For org X:

```
vertical_line(X) = ancestors(X) ∪ descendants(X)
```

This includes X itself, all orgs above it (parent, grandparent, up to root), and all orgs below it (children, grandchildren, etc.). It **excludes siblings** — other children of X's parent.

```
        Root
       /    \
      A      B          vertical_line(B) = {Root, B, B1, B2}
     / \    / \          (excludes A, A1, D)
    A1  .  B1  B2

    D (separate tree)    vertical_line(D) = {D}
```

## Algorithm

The DAG walk tracks one piece of state per path: `crossed_into` — the org where a foreign boundary was first crossed, or `null` if no crossing has occurred yet.

### Rules

1. **No crossing yet (`crossed_into = null`)**: check whether the next role's org is on the current org's vertical line.
   - **Yes** (vertical move): continue with `crossed_into = null`. Moving up to a parent or down to a child is always free.
   - **No** (lateral move): this is a **foreign crossing**. Set `crossed_into` to the next role's org.

2. **Already crossed (`crossed_into = X`)**: the next role's org must be on X's vertical line. If it is, continue (keeping `crossed_into = X`). If not, **block** — the role is not reachable on this path.

### Pseudocode

```
queue = [(role, null) for role in user.direct_roles]
visited = {}

while queue is not empty:
    (role, crossed_into) = queue.pop()
    if (role, crossed_into) in visited: skip
    visited.add((role, crossed_into))
    collect(role)

    for child_role in role.inclusions:
        if crossed_into is not null:
            # Already crossed — stay on crossed_into's vertical line
            if child_role.org not in vertical_line(crossed_into):
                block
            else:
                enqueue (child_role, crossed_into)
        else:
            # No crossing yet
            if child_role.org in vertical_line(role.org):
                enqueue (child_role, null)        # vertical move
            else:
                enqueue (child_role, child_role.org)  # foreign crossing
```

## Worked Example

### Setup

```
        Root Corp
       /         \
    Div A       Div B
   /              \
 Team A1        Team B1

 Ext D (separate tree, no parent)
```

**Exchanges:**
- Div A ↔ Div B (bilateral)
- Team B1 ↔ Ext D (bilateral)

**Roles and inclusions:**
- `Div B / Analyst` — has read on some Div B resource
- `Div A / Lead` includes `Div B / Analyst` (via exchange)
- `Div B / Analyst` includes `Team B1 / Intern` (vertical — B1 is child of B)
- `Team B1 / Intern` includes `Ext D / Viewer` (via exchange)

**User:** Alice, in Div A, directly assigned `Div A / Lead`.

### Trace

| Step | Role | crossed_into | Action |
|---|---|---|---|
| 1 | `Div A / Lead` | null | Collect. Start from user's direct role. |
| 2 | → `Div B / Analyst` | ? | Div B is not on vertical_line(Div A) = {Root, Div A, Team A1}. **Foreign crossing.** Set crossed_into = Div B. |
| 3 | `Div B / Analyst` | Div B | Collect. Check inclusions. |
| 4 | → `Team B1 / Intern` | Div B | Team B1 is in vertical_line(Div B) = {Root, Div B, Team B1}. **Allowed.** Keep crossed_into = Div B. |
| 5 | `Team B1 / Intern` | Div B | Collect. Check inclusions. |
| 6 | → `Ext D / Viewer` | Div B | Ext D is NOT in vertical_line(Div B) = {Root, Div B, Team B1}. **Blocked.** |

**Result:** Alice gets permissions from `Div A / Lead`, `Div B / Analyst`, and `Team B1 / Intern`. She does **not** get `Ext D / Viewer`'s permissions, even though there is a path through the inclusion graph.

### Why This Matters

Without the propagation limit, Alice would transitively gain Ext D's permissions through a chain she has no direct agreement with. The vertical-line rule ensures that after crossing into Div B's territory, only Div B's own hierarchy (up and down) is reachable — no lateral jumps to unrelated orgs.

## Edge Cases

### Same-tree exchanges

Two orgs in the same tree can have an exchange (e.g., Div A ↔ Div B, both under Root Corp). The vertical-line rule handles this correctly: moving from Div A to Div B is a lateral move (Div B is not an ancestor or descendant of Div A), so it triggers a foreign crossing. After that, only Div B's vertical line is available.

### Multiple exchanges on one path

If a role path crosses multiple exchange boundaries, only the **first** crossing sets `crossed_into`. Subsequent moves must stay within that first crossed-into org's vertical line. This is intentionally restrictive — it prevents chaining through multiple foreign orgs.

### @members chain

The @members auto-roles form a chain: child @members includes parent @members. This is a **vertical** move (child → parent), so it never triggers a foreign crossing. @members permissions always propagate freely up and down the org tree.

## At Scale

In a production system with ~10^3 orgs, the vertical line is computed from a **materialized path** stored per org (see [Architecture](/wiki/architecture)):

```
vertical_line(X):
  target.path LIKE X.path || '%'     -- X's descendants
  OR X.path LIKE target.path || '%'  -- X's ancestors
```

This replaces the recursive ancestor/descendant computation with an indexed string comparison, making the propagation check O(1) per edge during the DAG walk.
