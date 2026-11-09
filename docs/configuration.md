# Configuration

Settings go in `PLUGINS_CONFIG` in NetBox's `configuration.py`. All are
optional.

```python
PLUGINS_CONFIG = {
    'netbox_relationships': {
        'default_depth': 3,
        'max_depth': 8,
    },
}
```

| Setting | Default | What it does |
|---|---|---|
| `default_depth` | `3` | Hops a graph shows when it opens. |
| `max_depth` | `8` | Most hops any graph, impact analysis or API call may walk. |
| `max_nodes` | `1000` | Objects collected before a result is cut short (and says so). |
| `network_tiers` | `[]` | Device role slugs from the top of the network down, one list per tier. Turns network cables into uplinks. Not used while any tier exists under **Relationships → Network Tiers**. See [Network tiers](#network-tiers). |
| `tier_endpoints` | `True` | With tiers set, devices whose role is in no tier sit below the last tier, so a server uplinks to its switch. |
| `uplink_tag` | `'uplink'` | Interface tag that means "this device needs the far end of this cable". |
| `downlink_tag` | `'downlink'` | Interface tag that means "the far end needs this device". |
| `derived` | see below | Which links are read from NetBox's own data. |
| `object_types` | `[]` | Object types (`'dcim.device'`, ...) that get the card and tabs. Empty means the common ones. |
| `hidden_nodes` | `'placeholder'` | Objects a user may not view: `'placeholder'` shows "Hidden object", `'omit'` leaves them out. |
| `include_planned_in_impact` | `False` | Count *planned* relationships in impact analysis by default. |
| `layers` | `{}` | Service map layer per object type, for example `{'dcim.device': 'network'}`. Layers: `business`, `workload`, `compute`, `network`, `facility`. |

Changes to `object_types` need a NetBox restart.

## Derived links

Each kind can be switched on or off. Give only the ones to change:

```python
'derived': {'cables': False, 'placement': True},
```

| Key | Default | Link |
|---|---|---|
| `vm_cluster` | on | VM runs on its cluster, and on its device if pinned (hard). |
| `cluster_hosts` | on | Cluster runs on its devices (hard, as one redundancy group: one host failing leaves it at risk, all failing take it down). |
| `service_parent` | on | NetBox service runs on its device or VM (hard). |
| `cables` | on | Network cables, followed through patch panels: *uplinks to* between tiers, *is a peer of* within a tier, *connects to* (no impact) without tiers. |
| `power` | on | Device powered by its PDU or power feed (hard, all power supplies as one redundancy group); power feed fed by its panel (hard). |
| `circuits` | on | Circuit terminates at a site or provider network. |
| `virtual_chassis` | on | Virtual chassis runs on its members (hard, as one redundancy group). |
| `logical_parent` | on | Logical service consists of its child services. |
| `placement` | off | Device sits in its rack, location or site. |
| `ip_prefix` | off | IP address in its prefix, prefix in its VLAN. |

After a change, run:

```bash
python manage.py rebuild_relationship_index
```

The same rebuild runs as a NetBox system job every night.

## Network tiers

Without tiers, a cable only says that two devices are connected, and
carries no impact. With tiers, the plugin knows which end needs the other.

The easiest way is **Relationships → Network Tiers** in the UI: add a tier
per level of the network (level 1 at the top) and pick its device roles.
Changes apply straight away. While any tier exists there, the setting below
is not used. The setting does the same from `configuration.py`:

```python
'network_tiers': [
    ['border-router'],
    ['spine'],
    ['leaf', 'leaf-storage'],
],
```

Each entry is one tier, top of the network first, listing device role
slugs. Then, for every network cable path (patch panels and front/rear
ports in between are followed):

- different tiers: the device in the lower tier **uplinks to** the one in
  the higher tier. A hard dependency.
- same tier: the two are **peers**. No impact.
- devices with a role in no tier sit below the last tier
  (`tier_endpoints`), so servers, firewalls and access points uplink to
  their switch. With `tier_endpoints: False` they only *connect to* it.
- circuits sit above every tier: the device at a circuit's end needs it.
- management-only interfaces (out-of-band ports) are skipped at both
  ends: they never make a link.

A member of a virtual chassis (a stack, or two switches acting as one)
counts as the virtual chassis: the chassis has the uplinks, and runs on
its members. Several cables between the same two ends become one link
with a count.

All uplinks of one device or chassis back each other up (redundancy
group `uplinks`): losing one leaves it **at risk**, losing all takes it
**down**.

Where tiers can't tell (two switches in the same tier, daisy-chained),
tag the interface: `uplink` on the interface of the device that needs the
far end, or `downlink` on the other side.

After changing the setting, run `rebuild_relationship_index` (or **All
links → Rebuild now**). Tiers changed in the UI, and later cable, role and
tag changes, update the links by themselves.
