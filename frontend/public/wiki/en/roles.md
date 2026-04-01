# Roles

The **Roles** view is the central place for managing role definitions, inclusions, parent relationships, and resource permissions.

## Org-member roles (@members)

Each org has an auto-created **@members** role (shown with an `org` badge). It:
- Always contains all users in that org
- Includes its parent org's @members (permissions cascade up)
- Cannot have parent roles or be manually assigned/revoked

## Included roles & Parent roles

- **Included roles** — roles this role inherits permissions *from* (direct inclusions).
- **Parent roles** — roles that include *this* role (reverse direction).

Inclusions are split into two sections:
- **Own / Subtree** — roles from your org or its descendant orgs.
- **Foreign (via exchanges)** — roles from other orgs, made available through org exchanges.

## Foreign roles & Propagation limits

Roles from outside your org's ancestor/descendant chain are marked with a pink **foreign** badge. Foreign roles can only be included if they are exposed through an org exchange.

**Important:** When a role with foreign inclusions is itself shared externally (via an exchange), the foreign inclusions do not propagate. Only the role's own permissions and those from its org subtree are shared. This prevents unintended transitive cross-org permission sharing.

## Permission bits

Permissions use bitmasks per resource type:

| Type | Bits |
|------|------|
| document | read=1, write=2 |
| video | view=1, comment=2, stream=4 |

Click any bit in the permissions table to toggle it directly on the role.
