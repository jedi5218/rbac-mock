# Org Exchanges

The **Exchanges** view (available to org admins and superadmins) lets you manage **bilateral role-sharing agreements** between organizations.

## What is an exchange?

An exchange is a link between two organizations that allows each side to expose specific roles to the other. Once a role is exposed, admins of the partner org can include it in their own roles, just like they would with roles from their own org subtree.

## Creating an exchange

1. Click **+ New Exchange**.
2. Select your org (from your admin scope) and a partner org (outside your org subtree).
3. Ancestor/descendant pairs are not allowed (those already share through the @members chain).

## Exposing roles

After creating an exchange, each side can expose roles by selecting from a dropdown and clicking **Expose**. Only the admin who owns a role's org can expose or unexpose it.

## Closing an exchange

Either side can close the exchange. Closing will:
- Remove all cross-org role inclusions that depended on the exposed roles.
- Delete the exchange and all its exposed role records.

**Warning:** If the partner org exposed roles in the exchange, those will become inaccessible. Only the partner's admin can re-instate sharing by creating a new exchange.

## Propagation limits

When a role is included across an org boundary via an exchange, the foreign role's own foreign inclusions are **not** propagated further. This prevents chains like Org A -> Org B -> Org C from granting Org A unintended access to Org C's resources.

The Role Tree view shows blocked propagation with dimmed, struck-through role names and a `blocked` badge.
