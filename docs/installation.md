# Installation

## Install

1. Install the package into NetBox's virtual environment:

   ```bash
   source /opt/netbox/venv/bin/activate
   pip install git+https://github.com/mattivaisanen/netbox-relationships.git
   ```

   To keep it across NetBox upgrades, add the same line to
   `/opt/netbox/local_requirements.txt`.

2. Enable it in `configuration.py`, with any settings from
   [configuration.md](configuration.md):

   ```python
   PLUGINS = ['netbox_relationships']
   ```

3. Create the tables and the default relationship types, then read the
   links NetBox already holds:

   ```bash
   cd /opt/netbox/netbox
   python manage.py migrate netbox_relationships
   python manage.py rebuild_relationship_index
   ```

4. Restart NetBox and its worker:

   ```bash
   sudo systemctl restart netbox netbox-rq
   ```

## Permissions

| To do this | A user needs |
|---|---|
| See the card, tabs, graph and impact pages | `view_relationship` |
| Add, change or delete relationships | `add_`, `change_`, `delete_relationship` |
| Manage relationship types | `*_relationshiptype` |
| Manage logical services | `*_logicalservice` |

Objects in a graph or impact result also follow the user's own view
permissions on those objects.

## Upgrading

```bash
pip install --upgrade --force-reinstall --no-deps git+https://github.com/mattivaisanen/netbox-relationships.git
cd /opt/netbox/netbox && python manage.py migrate
sudo systemctl restart netbox netbox-rq
```

## Uninstalling

If the plugin is simply taken out of `PLUGINS`, NetBox keeps working: its
own tables are untouched. Some rows NetBox keeps about the plugin's objects
(change log entries, bookmarks, tag assignments) would then point at nothing
and can break the pages that list them. Remove it in this order instead:

1. `python manage.py prepare_relationships_uninstall` removes those rows.
   Add `--dry-run` to only list them.
2. `python manage.py migrate netbox_relationships zero` drops the plugin's
   tables.
3. Take `netbox_relationships` out of `PLUGINS` and restart NetBox.
4. `pip uninstall netbox-relationships`.
