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

## Permission labels

| Type | Bit | Label |
|------|-----|-------|
| document | 1 | read |
| document | 2 | write |
| video | 1 | view |
| video | 2 | comment |
| video | 4 | stream |
