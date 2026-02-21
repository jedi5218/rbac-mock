# Org Interactions

The **Interactions** view (available to org admins and superadmins) shows **lateral cross-org role relationships** — role inclusions that span organizationally unrelated orgs.

## What counts as an interaction?

A role inclusion between two roles from **different orgs** is an interaction, **unless** the two orgs are in an ancestor–descendant relationship (those are expected and normal via the @members chain).

## Reading the view

The view renders your visible org tree. Each org node shows:
- A count badge if it has cross-org interactions.
- Collapsible foreign-org panels listing each role link.

Each role link shows the direction:
- **⊃ includes** — this org's role includes a role from the foreign org.
- **⊂ included by** — this org's role is included by a role from the foreign org.

## Use case

Use this view to audit unexpected permission dependencies between teams or divisions that should be organizationally isolated.
