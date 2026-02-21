# Roles

The **Roles** view is the central place for managing role definitions, inclusions, parent relationships, and resource permissions.

## Public vs Private

| Visibility | Who can use as parent |
|------------|----------------------|
| **Public** | Any admin in the system |
| **Private** | Only admins whose org subtree contains the role's org |

Toggle visibility with the switch in the role detail header.

## Org-member roles (@members)

Each org has an auto-created **@members** role (shown with an `org` badge). It:
- Always contains all users in that org
- Is always public
- Includes its parent org's @members (permissions cascade up)
- Cannot have parent roles or be manually assigned/revoked

## Included roles & Parent roles

- **Included roles** — roles this role inherits permissions *from* (direct inclusions).
- **Parent roles** — roles that include *this* role (reverse direction).

Role graphs may contain cycles; the recursive permission resolution handles them safely via set-based deduplication.

## Foreign roles

Roles from outside your org's ancestor/descendant chain are marked with a pink **foreign** badge. You can still add public foreign roles as parents.

## Permission bits

Permissions use bitmasks per resource type:

| Type | Bits |
|------|------|
| document | read=1, write=2 |
| video | view=1, comment=2, stream=4 |

Click any bit in the permissions table to toggle it directly on the role.
