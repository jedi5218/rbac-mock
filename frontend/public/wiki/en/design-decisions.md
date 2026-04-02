# Design Decisions

This page explains the rationale behind key design choices in the RBAC system.

## Bitmask Permissions (not string sets)

Permissions are encoded as integer bitmasks rather than sets of strings like `["read", "write"]`.

**Advantages:**
- **Aggregation in SQL**: `BIT_OR` across thousands of rows in a single query. String sets would require array merging or UNION/DISTINCT operations.
- **Compact storage**: one integer per role-resource pair instead of a junction table per permission label.
- **O(1) permission check**: `(bits & required) = required` is a single CPU instruction. No set membership lookup.
- **Extensible per resource type**: adding a new permission to "video" (e.g., `upload = 8`) requires no schema change — just a wider bitmask.

**Tradeoff:** bitmask positions must be globally coordinated per resource type. This is manageable because resource types are defined centrally, not per-tenant.

## Role DAG (not flat role lists or trees)

Roles form a Directed Acyclic Graph, not a flat list (RBAC0) or a strict tree (RBAC1).

**Why DAG:**
- Roles naturally compose. A "Writer" role should include everything a "Reader" can do, plus write access. An "Admin" includes both "Writer" and "Auditor". This creates a diamond: Admin → Writer → Reader and Admin → Auditor → Reader.
- Trees cannot represent diamonds. A strict hierarchy forces duplication of the shared "Reader" permissions.
- Flat role lists require explicit enumeration of all permissions on every role, making maintenance quadratic in the number of roles.

**Why not arbitrary graphs (allow cycles):**
- Cycles in role inclusion are semantically meaningless (A includes B includes A adds nothing over A includes B).
- Cycles complicate traversal — BFS/DFS needs cycle detection to terminate.
- Blocking cycles at insertion is cheap (single reachability check) and eliminates an entire class of traversal bugs.

## @members Auto-Roles

Each org has a system-managed `@members` role that all org users are automatically assigned to. Child @members includes parent @members.

**Why:**
- **Baseline permissions without manual assignment**: every user in an org gets the org's baseline permissions without an admin remembering to assign roles.
- **Org-wide policy propagation**: set a permission on the root @members role and it cascades to every user in the tree. No need to assign roles org-by-org.
- **Consistent with the role DAG**: @members roles are regular roles in the DAG. No special permission resolution logic needed — the existing BFS handles them.

**Why child includes parent (not the reverse):**
- A child org's users should inherit the parent org's baseline permissions — e.g., all employees can read the company handbook.
- The inclusion direction is `child.@members → parent.@members`, meaning child users get parent permissions transitively.
- This is a **vertical** move in propagation terms, so it never triggers foreign crossing limits.

## Bilateral Exchanges (not global role sharing)

Cross-org role sharing requires an explicit exchange agreement between two orgs.

**Why bilateral, not a global role catalog:**
- **Trust boundaries**: org A shares roles with org B because they have an agreement. A global catalog would expose roles to all orgs by default, requiring opt-out rather than opt-in.
- **Revocability**: either side can close an exchange, and all dependent cross-org inclusions are automatically removed. Clean teardown of a specific partnership.
- **Audit**: each exchange is a discrete record with a creation timestamp. It's clear which orgs have agreements and what roles are exposed.

**Why canonical pair ordering:**
- Exchanges use `org_a_id < org_b_id` constraint to prevent duplicate exchanges between the same pair of orgs. Without this, two admins could independently create A↔B and B↔A, leading to confusing duplication.
- Ancestor-descendant pairs are rejected because they already share through the @members chain.

## Vertical-Line Propagation Limit

After a foreign crossing (role inclusion to an org outside the current vertical line), only the crossed-into org's vertical line remains reachable. See [Propagation Algorithm](/wiki/propagation) for the full walkthrough.

**Why not "block all foreign inheritance":**
- Too restrictive. If org A includes a role from org B (via exchange), and B has child org B1, it's natural for B1's roles to be reachable through B. The role came from B's organization; B's internal hierarchy should be respected.

**Why not "allow everything after crossing":**
- Transitive leaks. If A shares with B and B shares with C, unrestricted propagation would give A access to C's resources — without A and C having any agreement.

**Why vertical line (not just subtree):**
- Subtree-only would block upward propagation after crossing. If A includes a role from B, and B's @members includes Root's @members, the subtree rule would block the upward move to Root. But Root's permissions are by definition available to all descendants — blocking them is wrong.
- Vertical line allows both upward (to ancestors) and downward (to descendants) movement after crossing, while blocking lateral movement (to siblings or unrelated branches).

**Why lock to the first crossing:**
- After crossing into B, subsequent moves stay on B's vertical line. If B1 (child of B) has an exchange with D, D is not on B's vertical line, so it's blocked.
- This is intentionally conservative. Chaining through multiple foreign boundaries (A → B → D) would make permission provenance extremely difficult to audit.

## Pre-Computed Effective Permissions (at scale)

The demo computes effective permissions on demand via a Python-side DAG walk. At scale, this is replaced with a materialized `effective_permissions` table updated by background workers. See [Architecture](/wiki/architecture).

**Why not compute on demand at scale:**
- The DAG walk is O(roles x depth) per user. With 10^4 roles, each walk touches ~50 nodes. Acceptable for a single request, but multiplied by 10^6 users making frequent access checks, the aggregate load is prohibitive.
- Caching helps but doesn't eliminate the cold-start problem: after a role change invalidates the cache for 1000 users, the next 1000 requests all trigger full DAG walks simultaneously.

**Why materialized table, not just cache:**
- A cache (Redis) is fast but volatile. A materialized table survives restarts, provides a guaranteed fallback, and is queryable for analytics ("how many users can write to resource X?").
- The materialized table is the system of record for effective permissions. The cache is an acceleration layer on top.

**Why eventual consistency is acceptable:**
- Admin operations (role changes) are rare — maybe hundreds per day across the entire system. The delay between a change and its propagation is bounded (seconds for a background worker to process).
- Access checks use the most recently materialized state. In the worst case, a user retains a permission for a few seconds after it's revoked. For most RBAC use cases (not real-time security boundaries), this is acceptable.
- If stronger consistency is needed for specific resources, the system can bypass the cache and recompute on demand for those resources only.
