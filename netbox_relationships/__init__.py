"""
NetBox plugin for relationships and dependencies between any NetBox objects:
what an object needs, what needs it, and what stops working when it fails.
See README.md and docs/.
"""
from netbox.plugins import PluginConfig


class NetBoxRelationshipsConfig(PluginConfig):
    name = 'netbox_relationships'
    verbose_name = 'Relationships'
    description = (
        'Typed relationships between any NetBox objects, links NetBox already knows, '
        'a dependency graph, impact analysis and a layered service map.'
    )
    version = '0.1.0'
    author = 'Matti'
    base_url = 'relationships'
    # The oldest NetBox release the tests run on.
    min_version = '4.7.0'

    # See docs/configuration.md.
    default_settings = {
        # How many hops a graph shows when it opens, and the most any
        # graph, impact analysis or API call may walk.
        'default_depth': 3,
        'max_depth': 8,
        # Stop collecting objects after this many, so one request can't
        # load the whole database. The result then says it was cut short.
        'max_nodes': 1000,
        # Links worked out from NetBox's own data, by kind. Each one can be
        # switched off; run `manage.py rebuild_relationship_index` after a
        # change. See derived.py for what each kind adds.
        'derived': {
            'vm_cluster': True,       # VM runs on its cluster (and its device, if pinned)
            'cluster_hosts': True,    # cluster runs on its devices
            'service_parent': True,   # service runs on its device or VM
            'cables': True,           # device connects to device through cables
            'power': True,            # device powered by power feed / PDU; feed fed by panel
            'circuits': True,         # circuit terminates at site or provider network
            'virtual_chassis': True,  # device is a member of its virtual chassis
            'logical_parent': True,   # business service consists of its applications
            'placement': False,       # device sits in its rack, location or site
            'ip_prefix': False,       # IP address in prefix, prefix in VLAN
        },
        # Object types ('dcim.device', ...) whose pages get the
        # Relationships card and tabs. Empty: the common ones in
        # constants.TAB_MODELS.
        'object_types': [],
        # Objects a user may not view, in graphs and impact results:
        # 'placeholder' shows a grey "Hidden object", 'omit' leaves them out.
        'hidden_nodes': 'placeholder',
        # Count links with status "planned" in impact analysis by default.
        'include_planned_in_impact': False,
        # Service map layer per object type, over the defaults in
        # constants.DEFAULT_LAYERS: {'dcim.device': 'network', ...}.
        'layers': {},
    }

    menu = 'navigation.menu'
    template_extensions = 'template_content.template_extensions'

    def ready(self):
        super().ready()

        from . import jobs, signals, tabs  # noqa: F401 (registers jobs, receivers and tabs)
        signals.connect()
        tabs.register()


config = NetBoxRelationshipsConfig
