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
| `cluster_hosts` | on | Cluster runs on its devices (soft: one host failing leaves it degraded). |
| `service_parent` | on | NetBox service runs on its device or VM (hard). |
| `cables` | on | Devices connected by cables (symmetric, no impact). Power cables give *powered by* (hard). |
| `power` | on | Power feed fed by its panel (hard). |
| `circuits` | on | Circuit terminates at a site or provider network. |
| `virtual_chassis` | on | Device is a member of its virtual chassis. |
| `logical_parent` | on | Logical service consists of its child services. |
| `placement` | off | Device sits in its rack, location or site. |
| `ip_prefix` | off | IP address in its prefix, prefix in its VLAN. |

After a change, run:

```bash
python manage.py rebuild_relationship_index
```

The same rebuild runs as a NetBox system job every night.
