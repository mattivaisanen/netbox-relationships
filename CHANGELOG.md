# Changelog

## 0.2.0 (2026-11-09)

New:

- Network tiers: order device roles from the top of the network down
  (**Relationships → Network Tiers**, or the `network_tiers` setting), and
  network cables become "uplinks to" the device in the tier above, with
  impact. Cables are followed through patch panels.
  Devices in the same tier are peers. Interface tags `uplink` and
  `downlink` set the direction by hand.
- Virtual chassis members count as their chassis: the chassis has the
  uplinks and runs on its members. Several cables between the same two
  ends show as one link with a count.
- Redundancy groups and the new impact state *at risk*: a switch's
  uplinks, a cluster's hosts, a chassis' members and a device's power
  supplies back each other up. Losing one leaves what depends on them at
  risk; losing all takes it down. Relationships can be put in a group too.
- Each relationship can set its own impact and a label; the type only
  gives the default.
- Add what an object needs, or what needs it, many objects at a time, from
  the Relationships card or tab. The form asks what happens when the
  needed object fails.
- Path to the top on the Relationships tab: every chain of things an
  object stands on, its single points of failure and what is redundant.
- All links: every link, manual and from NetBox, with its origin and a
  Rebuild now button.
- "Add common types" on the relationship types list.
- The layered graph places what needs something above it, draws a virtual
  chassis as a box around its members, and shows devices by role.

Changed:

- New installs get four relationship types (Depends on, Runs on,
  Connects to, Related to). Existing installs keep all of theirs.
- The Relationships card and tab list links by meaning (needs, needed by,
  other) with their origin, instead of manual and derived apart.
- A cluster now *runs on* its hosts as a hard redundancy group instead of
  a soft link to each.
- A virtual chassis *runs on* its members instead of each member being
  "a member of" it with no impact.
- `manage.py migrate` rebuilds the link index, so links from NetBox show
  straight after an install or upgrade.

Fixed:

- Impact analysis said nothing when a switch failed; it now explains when
  an object has no links that carry impact.

## 0.1.0

First release.

- Relationship types with forward and reverse labels, impact (hard, soft,
  none), symmetric types, allowed object types, cardinality and loop checks.
  Eleven common types are created on install.
- Relationships between any two NetBox objects, with status and criticality.
- Logical services: business services, applications, components and
  external services, with owner, tenant and contacts.
- Links read from NetBox: VM to cluster, cluster to hosts, service to its
  device or VM, cables, power, circuits, virtual chassis and logical service
  parents. Rack placement and IP/prefix links are available but off.
- An edge index kept current by signals, a nightly rebuild job and the
  `rebuild_relationship_index` command.
- Relationships card, Relationships tab, Dependency graph tab and Impact
  button on object pages.
- Dependency graph with depth, direction and layout controls, and export to
  PNG, JSON and Mermaid.
- Impact analysis page with a "why" chain per affected object, and a
  service map per business service.
- REST API for all models, plus `graph/` and `impact/` endpoints.
- `prepare_relationships_uninstall` command.
