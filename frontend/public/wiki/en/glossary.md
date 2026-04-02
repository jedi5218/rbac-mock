# Glossary

## Organizations

**Org hierarchy** — Organizations form a tree via parent-child relationships. Each org has at most one parent. The root org has no parent.

**Org subtree** — An org and all its descendants (children, grandchildren, etc.). Used for admin scoping: an org admin manages their entire subtree.

**Vertical line** — For a given org X: the set of X's ancestors (up to root) plus X's descendants. Excludes siblings (other children of X's parent). Used to define [foreign propagation](/wiki/propagation) boundaries.

## Roles

**Role DAG** — Roles reference other roles through inclusions, forming a Directed Acyclic Graph. A role inherits all permissions from roles it includes, transitively. Cycles are detected and rejected before insertion.

**Role inclusion** — A directed edge in the role DAG. If role A includes role B, then A inherits all of B's permissions. Inclusions can span org boundaries when enabled by an exchange.

**Transitive closure** — The full set of roles reachable from a given role by following all inclusion chains. Used to compute effective permissions.

**@members role** — An auto-created system role, one per org (`is_org_role = true`). Every user in the org is automatically assigned to it. Each @members role includes its parent org's @members role, forming a chain that propagates baseline permissions up the org tree. Cannot be manually edited or deleted.

## Permissions

**Permission bitmask** — An integer encoding a set of permissions for a specific resource type. Each bit position represents a distinct permission. Current resource types:

| Type | Bit 1 | Bit 2 | Bit 4 |
|---|---|---|---|
| document | read | write | — |
| video | view | comment | stream |

**BIT_OR aggregation** — The method for combining permissions across multiple roles. If role A grants `read` (bit 1) and role B grants `write` (bit 2), the effective permission is `read + write` (bits 1 | 2 = 3). Permissions only accumulate — one role cannot revoke what another grants.

**Effective permissions** — The final set of permissions a user has on each resource, computed by walking the role DAG from all directly assigned roles, collecting all role-resource permission pairs, and aggregating with BIT_OR.

## Exchanges

**Org exchange** — A bilateral agreement between two organizations that enables cross-org role sharing. Each side can expose specific roles to the partner. Stored with canonical ordering (`org_a_id < org_b_id`) to prevent duplicates.

**Exposed role** — A role that an org has made available to its exchange partner. Only the role's owning org can expose or unexpose it. Once exposed, the partner's admins can include it in their own roles.

**Foreign role** — A role belonging to an org outside the current user's ancestor/descendant chain. Foreign roles can only be included if they are exposed through an active exchange.

**Foreign crossing** — The event during role DAG traversal when a role inclusion crosses to an org outside the current org's vertical line. After a crossing, only the crossed-into org's vertical line remains reachable. See [Foreign Propagation](/wiki/propagation).

## Architecture Concepts

These terms appear in the [production architecture](/wiki/architecture) overview.

**Materialized path** — A string encoding an org's position in the hierarchy (e.g., `/root/div-a/team-alpha/`). Replaces recursive queries with indexed string operations for subtree and ancestor lookups.

**Closure table** — A table storing all (ancestor, descendant, depth) pairs for a hierarchy. Alternative to materialized paths. Pre-computes transitive relationships for O(1) lookups.

**Materialized effective permissions** — A pre-computed table mapping (user_id, resource_id) to permission bits. Updated asynchronously when the role graph changes. Makes access checks O(1) instead of requiring a DAG walk per request.

**CQRS (Command Query Responsibility Segregation)** — Architectural pattern separating read and write operations. In this system: reads (access checks) hit a pre-computed table; writes (admin ops) update source tables and trigger background recomputation.

**Cache invalidation scope** — The set of cached entries that must be refreshed after a specific change. Ranges from a single user (role assignment) to all users in two org subtrees (exchange creation/closure).
