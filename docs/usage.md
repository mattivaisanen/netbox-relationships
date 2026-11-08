# Using the plugin

## How a relationship reads

Every relationship reads **source → target** as "source needs target".
*Web front-end depends on Order database* means the front-end needs the
database. When the target fails, the source is affected; the other way
round, nothing happens.

Symmetric types (*connects to*, *peer of*, *related to*) have no direction
and are shown without an arrow.

## Relationship types

**Relationships → Types** lists the types. Eleven are created on install
and can be changed or removed. A type sets:

- **Forward / reverse label**: how the link reads from each end
  (*depends on* / *is required by*).
- **Impact**: *hard* (a failure takes the source down), *soft* (the source
  keeps running, degraded) or *none* (documentation only).
- **Source / target types**: which objects may be linked. Empty allows any.
- **Cardinality**: limits such as "a source has at most one target".
- **Allow cycles**: off by default, so A → B → A is refused.
- **Require description** and a **colour** for graphs.

## Adding relationships

- From any object's page: **Add relationship** on the Relationships card
  fills in that object as the source.
- From **Relationships → Relationships → Add**: pick both ends from any
  object type.
- In bulk: **Import** takes CSV, JSON or YAML with `type`, `source_type`,
  `source_name` (or `source_id`), `target_type` and `target_name` (or
  `target_id`).

When an object is deleted, its relationships are deleted with it and the
change log records each one.

## Logical services

**Relationships → Logical services** holds things that have no NetBox
object of their own:

| Kind | For |
|---|---|
| Business service | What users or customers rely on, such as online ordering. |
| Application | A piece of software that delivers part of a business service. |
| Component | A part of an application, such as a queue or a cache. |
| External | Something outside your network, such as a payment provider. |

A service's **parent** puts it inside another (an application inside a
business service). Link services to the VMs, devices and NetBox services
they run on with ordinary relationships.

## Links read from NetBox

Some links are worked out from NetBox's own data and appear in grey,
dotted, under "Derived" headings. They can't be edited here; change the
NetBox object instead and the link follows. Which kinds are on is set in
[configuration.md](configuration.md#derived-links).

## On object pages

- **Relationships card** (right column): how many objects this one needs and
  how many need it, the most critical of those, and buttons to add a link
  or open the graph.
- **Relationships tab**: every link in both directions, manual and derived.
- **Dependency graph tab**: the graph around the object. Choose depth,
  direction (needs, needed by or both), layout, and whether to show derived
  links. Click an object to highlight its chain, double-click to open it.
  Export as PNG, JSON or Mermaid.
- **Impact button**: opens impact analysis for this object.

## Impact analysis

**Relationships → Impact analysis** takes one or more objects and shows
what stops working if they fail:

- **Down**: reached over a hard link from something that failed or is down.
- **Degraded**: reached over a soft link, or over a hard link from something
  only degraded.

Each affected object shows the chain back to the failed object. The summary
lists affected business services, owners and tenants. Choose **Maintenance**
to plan downtime; the result is the same, only the wording changes.
Relationships with status *planned* are left out unless you tick
**Include planned**.

## Service map

**Relationships → Service map**, or the button on a business service, shows
everything the service needs in layers: business, workloads, compute and
storage, network, facility. Open it from impact analysis to colour each box
by its state.
