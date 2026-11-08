# netbox-relationships

A NetBox plugin that records **what depends on what**. NetBox already knows
where things are and how they are cabled. This plugin adds the part it is
missing: which application runs on which virtual machine, which database a
service needs, which power feed keeps a rack alive, and which business
service falls over when any of those fail.

Use it to answer two questions:

- **"If this breaks, what stops working?"** Pick one or more objects and see
  everything that goes down or runs degraded because of them, with the chain
  of links that explains why.
- **"How is this put together?"** Open any object and see what it needs and
  what needs it, as a list or as an interactive graph.

## What it adds

- **Relationships** between any two NetBox objects, of a type you choose:
  *depends on*, *runs on*, *sends data to*, *backed up by* and more. Each
  type says whether a failure passes through it (hard), weakens what is
  above it (soft) or does not matter (none). Loops and disallowed object
  pairs are refused.
- **Links read from NetBox itself**, kept current automatically: virtual
  machines on clusters, services on devices, cables, power feeds, circuits
  and virtual chassis members. Rack placement and IP/prefix links can be
  switched on.
- **Logical services**: business services, applications and external
  services that have no NetBox object of their own.
- On object pages: a **Relationships** card, a **Relationships** tab, a
  **Dependency graph** tab and an **Impact** button.
- An **impact analysis** page, a layered **service map** for each business
  service, and a REST API for the graph and impact results.

Graphs and impact results only show objects the user may view. Others
appear as "Hidden object".

## Requirements

- NetBox 4.7 or later.
- No other plugins or Python packages. The graph library (Cytoscape.js) is
  bundled; nothing is loaded from the internet.

## Installation

```bash
pip install git+https://github.com/mattivaisanen/netbox-relationships.git
```

```python
# configuration.py
PLUGINS = ['netbox_relationships']
```

```bash
cd /opt/netbox/netbox && python manage.py migrate netbox_relationships
python manage.py rebuild_relationship_index
sudo systemctl restart netbox netbox-rq
```

Give users the `netbox_relationships` permissions they need under
**Admin → Permissions**. See [docs/installation.md](docs/installation.md).

## Upgrading

```bash
pip install --upgrade --force-reinstall --no-deps git+https://github.com/mattivaisanen/netbox-relationships.git
cd /opt/netbox/netbox && python manage.py migrate
```

Then restart NetBox. The [changelog](CHANGELOG.md) lists what each version
needs.

## Uninstalling

The plugin never changes NetBox's own tables, so NetBox keeps working if it
is removed. To remove it cleanly:

```bash
cd /opt/netbox/netbox
python manage.py prepare_relationships_uninstall
python manage.py migrate netbox_relationships zero
```

Then take `netbox_relationships` out of `PLUGINS`, restart NetBox and
`pip uninstall netbox-relationships`.

## Documentation

- [Installation, upgrading and uninstalling](docs/installation.md)
- [Using the plugin](docs/usage.md)
- [Configuration](docs/configuration.md)
- [REST API](docs/api.md)
- [Developer notes](DEVELOPER.md)
- [Changelog](CHANGELOG.md)

## License

Apache License 2.0, see [LICENSE](LICENSE). Includes
[Cytoscape.js](https://js.cytoscape.org) 3.30.2 (MIT, see
`netbox_relationships/assets/LICENSE-cytoscape.txt`).
