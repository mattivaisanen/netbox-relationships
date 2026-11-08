# Changelog

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
