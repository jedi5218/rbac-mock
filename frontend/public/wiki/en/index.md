# RBAC Mockup — Wiki

Welcome to the documentation for the Role-Based Access Control demo system.

## Views

- [Organizations](/wiki/orgs) — hierarchical org tree, admin scoping, @members roles
- [Users](/wiki/users) — user management, org assignment, role assignment
- [Roles](/wiki/roles) — role DAG with inclusions, permission inheritance
- [Resources](/wiki/resources) — documents and videos with per-role bitmask permissions
- [Resolve](/wiki/resolve) — compute effective permissions for a user across the full role tree
- [Exchanges](/wiki/exchanges) — cross-org role sharing via bilateral agreements
- [Role Tree](/wiki/role-tree) — visual role inclusion hierarchy per user

## Key Concepts

### Permission Bitmasks

Each resource type uses a different bit encoding:

| Resource Type | Bit 1 | Bit 2 | Bit 4 |
|---------------|-------|-------|-------|
| document      | read  | write | —     |
| video         | view  | comment | stream |

Effective permissions are computed by **BIT_OR** across all transitively included roles.

### Role Inclusion DAG

Roles can include other roles, forming a directed acyclic graph. A role inherits all permissions from its included roles. Cycles are detected and blocked before insertion.

### Org Hierarchy & Scoping

Organizations form a tree. **Superadmins** manage everything. **Org admins** manage their org and all descendants. Regular users see only their own org.

### Foreign Propagation Limits

When a role crosses an org boundary via an exchange, its own foreign inclusions do not chain further. This prevents unintended transitive permission leaks across organizations.

## Demo Reset

This is a live demo. You can reset all data to its initial state at any time using the **Reset Demo** button in the navigation bar.

Default password for all demo users: `admin123`
