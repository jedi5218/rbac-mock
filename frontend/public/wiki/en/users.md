# Users

The **Users** view lists all users visible in your admin scope, and lets you create, edit, and manage role assignments.

## Org membership

Every user belongs to exactly one organization. When a user is created or moved to a different org, they are automatically added to that org's **@members** role and removed from the previous org's @members role.

## Flags

- **Superadmin** — can manage all orgs, users, roles, and resources across the entire system.
- **Org admin** — can manage users, roles, and resources within their org subtree.

## Role assignment

Use the **Roles** button on any user row to assign or revoke roles. Note:

- **@members** roles are managed automatically and cannot be manually assigned or revoked.
- Org admins can only assign roles that are within their own org subtree or exposed via an org exchange.

## Editing users

Click **Edit** to modify a user's name, email, or password.

- **Superadmins** can also change the user's org and flags.
- **Org admins** can toggle the `is_org_admin` flag for users in their subtree.
