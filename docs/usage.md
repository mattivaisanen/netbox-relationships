# Using the plugin

## How a relationship reads

Every relationship reads **source → target** as "source needs target".
*Web front-end depends on Order database* means the front-end needs the
database. When the target fails, the source is affected; the other way
round, nothing happens.

Symmetric types (*connects to*, *peer of*, *related to*) have no direction
and are shown without an arrow.

## Relationship types

**Relationships → Relationship Types** lists the types. A new install
gets four: *Depends on*, *Runs on*, *Connects to* and *Related to*.
**Add common types** on that list adds seven more (*sends data to*,
*backed up by*, *replicates to*, *managed by*, *monitored by*, *powered
by*, *peer of*). Upgrades never add, change or remove types. A type sets:

- **Forward / reverse label**: how the link reads from each end
  (*depends on* / *is required by*).
- **Impact**: the default for its links: *hard* (a failure takes the
  source down), *soft* (the source keeps running, degraded) or *none*
  (documentation only). Each relationship can set its own.
- **Source / target types**: which objects may be linked. Empty allows any.
- **Cardinality**: limits such as "a source has at most one target".
- **Allow cycles**: off by default, so A → B → A is refused.
- **Require description** and a **colour** for graphs.

## Adding relationships

- From any object's page: **Needs…** or **Needed by…** on the
  Relationships card (or *Add what it needs* / *Add what needs it* on the
  Relationships tab). Pick an object type and any number of objects; one
  relationship is made for each. The form asks what happens when what is
  needed fails: *stops working* (hard), *works, but worse* (soft) or *not
  affected* (none).
- From **Relationships → Manual Relationships → Add**: one relationship,
  both ends from any object type.
- In bulk: **Import** takes CSV, JSON or YAML with `type`, `source_type`,
  `source_name` (or `source_id`), `target_type` and `target_name` (or
  `target_id`), plus optional `impact`, `label`, `group` and `group_min`.

Each relationship can have a **label**, a few words on what it is for
("nightly export", "login"). It is shown on the graph and in lists.

## Redundancy

Links from the same object with the same **redundancy group** name back
each other up. **Needs at least** says how many of them must work. With
two database replicas in group *databases* needing 1, losing one leaves
the application **at risk** (still working, without a spare); losing both
takes it **down**. In the add form, tick *These back each other up*.

Links from NetBox use groups by themselves: a switch's uplinks, a
cluster's hosts, a virtual chassis' members and a device's power supplies.

## All links

**Relationships → All Links** lists every link: the ones added by hand and
the ones worked out from NetBox, with their origin. Filter by origin or
impact. **Rebuild now** works out every link from NetBox again (the same
runs nightly and after `manage.py migrate`).

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

Some links are worked out from NetBox's own data. They are drawn dotted
and marked *NetBox* with where they come from (cables, virtual chassis,
cluster hosts...). They can't be edited here; change the NetBox object
instead and the link follows. Which kinds are on is set in
[configuration.md](configuration.md#derived-links).

Network cables only carry impact once **network tiers** are set (device
roles from the top of the network down). Then a switch *uplinks to* the
switch above it, through any patch panels, and impact analysis follows
the whole network. See [configuration.md](configuration.md#network-tiers).

## On object pages

- **Relationships card** (right column): how many objects this one needs,
  how many need it and how many other links it has, the most important of
  them, and buttons to add links or open the graph.
- **Relationships tab**: three tables, *Needs*, *Needed by* and *Other
  links* (connections and notes with no impact), each mixing manual links
  and links from NetBox with their origin. Below them, **Path to the top**:
  every chain of things the object stands on, its **single points of
  failure** (one of them failing takes it down) and what is **redundant**
  (one failing leaves it at risk).
- **Dependency graph tab**: the graph around the object. Choose depth,
  direction (needs, needed by or both), layout, and whether to show derived
  links. The layered layout puts what needs something above it, draws a
  virtual chassis as a box around its members and shows how many cables a
  link stands for. Click an object to highlight its chain, double-click to
  open it.
  Export as PNG, JSON or Mermaid.
- **Impact button**: opens impact analysis for this object.

## Impact analysis

**Relationships → Impact analysis** takes one or more objects and shows
what stops working if they fail:

- **Down**: reached over a hard link from something that failed or is down.
- **Degraded**: reached over a soft link, or over a hard link from something
  only degraded.
- **At risk**: still working, but lost part of a redundancy group (one of
  two uplinks, one host of a cluster).

When nothing is affected, the page says why: the object has no links, or
none of its links carry impact.

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
