# Organizations

The **Organizations** view shows the org hierarchy as an interactive tree. Every user, role, and resource in the system belongs to exactly one organization.

## Hierarchy

Organizations form a parent–child tree of arbitrary depth. A root org has no parent. Any org can have multiple children.

```
Root Corp
└── Division A
    ├── Team Alpha
    └── Team Beta
```

## Admin scope

- **Superadmins** can see and manage all organizations.
- **Org admins** can see their own org and all descendants.
- **Regular users** see only their own org.

## @members role

Every org automatically has an **@members** role that always contains all users in that org. It is public, auto-managed, and cannot be manually assigned or have parent roles. Child org `@members` roles include the parent org's `@members`, so permissions cascade down the hierarchy.

## Actions

| Action | Who | Notes |
|--------|-----|-------|
| Create | Superadmin | Can be placed anywhere in the tree |
| Edit | Superadmin | Rename or re-parent |
| Delete | Superadmin | Requires no children, no users, no non-system roles |
