# Developer guide

How the plugin is put together, and why.

## Ground rules

- **NetBox 4.7+ only**, through documented plugin extension points:
  generic views, `register_model_view`, `PluginTemplateExtension`,
  `get_model_urls`, NetBox's form, table, filter set and REST API base
  classes. No monkey-patching.
- **No dependencies** beyond NetBox. Cytoscape.js 3.30.2 is bundled in
  `assets/` and served by the plugin, so `collectstatic` is not needed.
- **NetBox's own tables are never changed.** Objects are referred to by
  content type and ID. Removing the plugin leaves NetBox working.
- **No database queries at startup.** Form querysets are lazy.

## Module map

| Module | Responsibility |
|---|---|
| `models.py` | `RelationshipType`, `Relationship`, `LogicalService`, `NetworkTier` and the `EdgeIndex` table. |
| `validation.py` | Checks run by `Relationship.clean()`: allowed types, self links, duplicates, cardinality, loops. |
| `derived.py` | Providers that read links from NetBox data (VM → cluster, cables, power, ...). Each one lists the models it watches. |
| `topology.py` | Turns network cable paths into uplinks, peer links or plain connections, using the `network_tiers` setting. |
| `paths.py` | "Path to the top" on the Relationships tab: chains, single points of failure, redundant objects. |
| `edges.py` | Writes `EdgeIndex` rows: one relationship, one provider for some objects, or a full rebuild. |
| `signals.py` | Keeps the index current: relationship save/delete, provider-watched models, removal of an object's relationships when it is deleted, and a full rebuild after `migrate`. |
| `jobs.py`, `management/commands/` | Nightly rebuild job, `rebuild_relationship_index`, `prepare_relationships_uninstall`. |
| `graph.py` | Walks the index around objects and returns nodes and edges the user may see. |
| `impact.py` | Failure propagation and the "why" chain. |
| `servicemap.py` | Sorts a business service's graph into layers. |
| `tabs.py`, `template_content.py` | Tabs, card and Impact button on other models' pages. |
| `assets.py`, `assets/` | Cytoscape.js, `graph.js` (draws the graph, layered layout, export), `addmany.js` (the add-several form) and `graph.css`. |
| `views.py`, `forms.py`, `filtersets.py`, `tables.py`, `urls.py`, `navigation.py`, `search.py`, `api/` | Standard NetBox UI and REST API. |
| `settings.py`, `constants.py`, `choices.py` | Settings access, fixed lists, choice sets. |

## The edge index

Graphs and impact analysis never read relationships or NetBox models
directly. They read `EdgeIndex`, one row per link:

- `origin = 'manual'`: a `Relationship`, linked one-to-one.
- any other `origin`: a provider key from `derived.py`. `owner_type` and
  `owner_id` name the object the row was read from, so a change to that
  object replaces only its rows.

Labels, impact, symmetry and colour are copied onto each row, so a walk
needs no joins. Changing a type updates its rows (`edges.sync_type`),
except the impact of relationships that set their own.

Rows also carry a redundancy `group` and `group_min` (see Impact), a
`link_count` (parallel cables folded into one link) and a `note` (a
relationship's label, or "2 cables").

The index is a cache. If it is ever wrong, `rebuild_relationship_index`
rebuilds it from scratch; the nightly job does the same.

## Direction

A row always reads source → target as "source needs target". Walking
*down* follows source → target, walking *up* follows target → source.
Symmetric rows are followed both ways in both walks.

## Walking the graph

`graph.walk()` is breadth-first, one level at a time. Each level is one
query: all rows whose near end is in the current frontier, grouped by
content type into `(type = X AND id IN (...)) OR ...`. So the number of
queries grows with depth, not with the number of objects. The walk stops
at `max_depth` or after `max_nodes` objects.

`graph.resolve()` then loads the objects, one query per content type,
restricted to what the user may view. Objects outside that become hidden
placeholders with no name.

## Network topology

NetBox keeps a `CablePath` for every interface: the far end, through any
patch panels. Tiers come from `NetworkTier` rows when any exist, else from
the `network_tiers` setting. Saving a tier, or changing its roles, reruns
the two uplink providers over everything once the transaction commits
(`edges.refresh_network`). `topology.Links` reads those paths for a set of *nodes* (a
device, or its virtual chassis if it is a member), and decides each
link's direction from the device roles' tiers, with `uplink`/`downlink`
interface tags overriding.

Each link has exactly one owner, so a refresh rewrites only its own rows:
the node that needs the other (an uplink), or the node with the lower key
(peers and plain connections). Links to circuits are owned by the device
end. Two providers share this code: `DeviceUplinkProvider` (owner: devices
outside a chassis) and `ChassisUplinkProvider` (owner: virtual chassis).

They refresh on a saved or deleted `CablePath` (both ends), a saved device
(itself and its neighbours, since a role change can turn their links
around) and a saved or deleted `TaggedItem` on an interface. A device
leaving a virtual chassis is picked up by the nightly rebuild.

## Impact

`impact.analyse()` walks *up* from the failed objects over rows with impact
`hard` or `soft`. States only get worse (at risk → degraded → down), so
the walk ends. Each affected object keeps the row that last set its state;
following those back gives the chain.

Hard rows with a `group` count together per source: the source goes down
when fewer than `group_min` of the group's targets still work, and is *at
risk* while any of them is lost. Each round collects the groups it touched
and loads all of their rows in one query.

`paths.analyse()` loads an object's whole dependency subgraph once, then
fails each object in it in memory (`paths.simulate`, same rules) to find
single points of failure. No queries per candidate.

## Tests

`python manage.py test netbox_relationships` from NetBox's `netbox/`
folder. The suite is small on purpose: validation, index updates,
impact propagation with redundancy, per-link impact, one derived provider,
uplinks through a patch panel to a virtual chassis, and the uninstall
command.
