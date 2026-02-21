# Resources

The **Resources** view lists all resources visible in your admin scope, and lets you create and edit them along with their role permission grants.

## Resource types

| Type | Available permissions |
|------|-----------------------|
| **document** | read, write |
| **video** | view, comment, stream |

## Org scoping

Each resource belongs to one org. Roles can only be granted permissions on resources within the **same org**. Cross-org resource access must be arranged via role inclusions.

## Role permissions in create/edit

When you create or edit a resource, a **Role permissions** section shows all non-system roles in the same org. Click any permission bit to toggle it on or off for that role.

Changes are saved atomically when you click **Save** / **Create** — only modified bits are written to the database.
