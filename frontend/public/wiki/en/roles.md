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

**Vertical-line rule:** When a role inclusion crosses an org boundary (a "foreign crossing"), further propagation is restricted to the crossed-into org's **vertical line** — its ancestors and descendants, but not its siblings or other branches. This allows natural up/down propagation within the foreign org's hierarchy while preventing transitive leaks to unrelated orgs.

For example: if your role includes a role from Org B (via exchange), you also receive permissions from B's parent and child orgs through the inclusion chain. But if B's child has an exchange with Org D, D's roles are blocked — they fall outside B's vertical line.

See [Propagation Algorithm](/wiki/propagation) for a detailed walkthrough with examples.

## Permission bits

Permissions use bitmasks per resource type:

| Type | Bits |
|------|------|
| document | read=1, write=2 |
| video | view=1, comment=2, stream=4 |

Click any bit in the permissions table to toggle it directly on the role.
