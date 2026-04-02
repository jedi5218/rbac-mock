# Production Architecture

This demo runs as a single process with an in-memory cache. At production scale (~10^6 users, ~10^5 resources, ~10^4 roles, ~10^3 orgs), the architecture separates into distinct layers with different performance characteristics.

## Two-Path Design

All operations fall into one of two paths with fundamentally different requirements:

### Read Path (Access Checks)

The hot path. Every user action triggers a check: "can user X perform action Y on resource Z?" This must be **O(1)** — a single indexed lookup, not a graph traversal.

Effective permissions are **pre-computed** and stored in a materialized table:

```
effective_permissions (user_id, resource_id, permission_bits)
```

An access check becomes:

```sql
SELECT 1 FROM effective_permissions
WHERE user_id = :uid AND resource_id = :rid
  AND (permission_bits & :required_bits) = :required_bits
```

A Redis cache layer sits in front of this table. Cache hits avoid the database entirely.

### Write Path (Admin Operations)

Role graph changes — adding an inclusion, changing a permission, assigning a role — are infrequent but have wide blast radius. A single role inclusion change can affect thousands of users.

Write operations:
1. Validate (cycle check, exchange check, propagation rules)
2. Write to source-of-truth tables
3. Enqueue a recomputation job
4. Background worker finds affected users and updates the materialized table

The write path is **eventually consistent**: there is a brief window (seconds) between a role change and the updated effective permissions being visible. This is acceptable because admin operations are rare relative to access checks, and the window is bounded.

## Component Overview

```
                    ┌───────────────────────────────┐
                    │     API Layer (stateless)      │
                    │   horizontally scalable        │
                    ├───────────────┬────────────────┤
                    │ Access checks │ Admin ops      │
                    │ (read path)   │ (write path)   │
                    └──────┬────────┴───────┬────────┘
                           │                │
                    ┌──────▼──────┐  ┌──────▼──────┐
                    │    Redis    │  │  Job Queue   │
                    │   (cache)   │  │ (recompute)  │
                    └──────┬──────┘  └──────┬──────┘
                           │                │
                    ┌──────▼────────────────▼──────┐
                    │      Primary Database         │
                    │                               │
                    │  Source of truth:              │
                    │    orgs, roles, inclusions,    │
                    │    resources, permissions,     │
                    │    user_roles, exchanges       │
                    │                               │
                    │  Materialized:                 │
                    │    effective_permissions       │
                    └───────────────────────────────┘
```

## Org Hierarchy at Scale

With ~10^3 orgs in a ~10-level hierarchy, recursive queries (CTEs) work but are wasteful for the frequent operations: subtree checks, ancestor lookups, and vertical-line computation.

### Materialized Path

Each org stores its full path from root:

| id | name | path |
|---|---|---|
| 1 | Root Corp | `/1/` |
| 42 | Division A | `/1/42/` |
| 167 | Team Alpha | `/1/42/167/` |

Common queries become string operations:

| Query | SQL |
|---|---|
| Is X in Y's subtree? | `X.path LIKE Y.path \|\| '%'` |
| Is X an ancestor of Y? | `Y.path LIKE X.path \|\| '%'` |
| X's vertical line (ancestors + descendants) | `X.path LIKE target.path \|\| '%' OR target.path LIKE X.path \|\| '%'` |
| All orgs in subtree | `WHERE path LIKE '/1/42/%'` |

All indexed. All O(1) per lookup. Path is updated on org move (rare).

### Alternative: Closure Table

Store all (ancestor_id, descendant_id, depth) pairs explicitly. ~10^3 orgs x 10 depth = ~10^4 rows. Supports the same queries via joins instead of string matching. Better for databases without efficient LIKE indexing.

## Role DAG Recomputation

The role inclusion graph has ~10^4 roles with ~3 inclusions each on average (~30K edges). A BFS per user touches ~50 roles. This is affordable even in bulk.

### Incremental Recomputation

When a role inclusion changes (e.g., role R1 now includes R2):

1. **Find affected users**: walk the reverse inclusion graph upward from R1 to find all roles that transitively include R1, then find all users assigned to any of those roles.
2. **Recompute each user**: run the forward DAG walk (with foreign propagation rules) for each affected user.
3. **Update materialized table**: diff old and new effective permissions, apply changes.
4. **Invalidate cache**: remove affected user entries from Redis.

With ~1000 affected users and ~50 roles per walk, a single recomputation batch is ~50K role visits — completes in seconds on a background worker.

### Permission Change

When a role's own permission bits change (not the graph structure), the same recomputation applies but the set of affected users is exactly those who transitively hold that role. No graph structure change needed.

### User Role Assignment

When a user is assigned/unassigned a role, only that user's effective permissions need recomputation. This is the cheapest case.

## Cache Invalidation Strategy

| Event | Invalidation scope |
|---|---|
| User assigned/unassigned a role | That user only |
| Role permission bits changed | All users who transitively hold that role |
| Role inclusion added/removed | All users who transitively hold the parent role |
| Role deleted | All users who held it (directly or transitively) |
| Org exchange created/closed | All users in both orgs' subtrees |

**TTL as safety net**: all cache entries expire after a bounded period (e.g., 1 hour). This caps the staleness window even if an invalidation event is missed.

## Numbers at Scale

| Entity | Count | Storage impact |
|---|---|---|
| Organizations | ~10^3 | Closure table: ~10^4 rows |
| Users | ~10^6 | user_roles: ~3M rows (avg 3 roles/user) |
| Roles | ~10^4 | Inclusion edges: ~30K |
| Resources | ~10^5 | — |
| Effective permissions | ~10^6 users x ~20 resources avg | ~20M rows |
| Recomputation on role change | ~1K affected users | Seconds in background |
| Access check latency | — | <1ms (cache hit) / <5ms (DB lookup) |

The effective_permissions table is the largest (~20M rows) but has a simple two-column primary key. Standard B-tree indexing handles this comfortably.

## What the Demo Simplifies

| Aspect | Demo | Production |
|---|---|---|
| Permission resolution | On-demand DAG walk per request | Pre-computed, materialized table |
| Cache | In-process Python dict | Redis cluster |
| Org hierarchy queries | Recursive CTEs | Materialized path or closure table |
| Recomputation | N/A (computed on read) | Background workers with job queue |
| Consistency | Immediate (single process) | Eventually consistent (bounded delay) |
| Horizontal scaling | Single uvicorn process | Stateless API behind load balancer |
