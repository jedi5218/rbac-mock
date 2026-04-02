# Resolve Effective Permissions

The **Resolve** view computes and displays the full set of effective permissions for any user visible in your admin scope.

## How resolution works

1. Start with all roles directly assigned to the user.
2. Recursively follow all role inclusions (the full role graph, handling cycles).
3. Collect all `(resource, permission_bits)` pairs from every reached role.
4. Aggregate with `BIT_OR` — a user gets the union of all permissions across all reachable roles.

## Caching

Resolution results are cached in-process. The cache is invalidated:
- **Per user** when their role assignments change.
- **Globally** when any role permission or role inclusion changes.

## Foreign propagation

When traversing the role DAG, cross-org inclusions (via exchanges) are subject to **vertical-line propagation limits**. After crossing into a foreign org, only that org's ancestors and descendants are reachable — not siblings or unrelated branches. See [Propagation Algorithm](/wiki/propagation).

## At scale

This demo resolves permissions on demand via a Python-side DAG walk. In a production system (~10^6 users), effective permissions are **pre-computed** into a materialized table and updated by background workers when the role graph changes. Access checks become O(1) lookups instead of graph traversals. See [Architecture](/wiki/architecture).

## Permission labels

| Type | Bit | Label |
|------|-----|-------|
| document | 1 | read |
| document | 2 | write |
| video | 1 | view |
| video | 2 | comment |
| video | 4 | stream |
