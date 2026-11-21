"""Fixed lists the plugin works from."""

#: Origin of an edge index row entered by hand. Derived rows carry their
#: provider's key instead (see derived.py).
MANUAL = 'manual'

#: Object types whose pages get the Relationships card and tabs when the
#: `object_types` setting is empty.
TAB_MODELS = (
    'dcim.device', 'dcim.rack', 'dcim.site', 'dcim.location', 'dcim.powerfeed', 'dcim.powerpanel',
    'dcim.virtualchassis', 'virtualization.virtualmachine', 'virtualization.cluster', 'ipam.service',
    'ipam.prefix', 'ipam.vlan', 'ipam.ipaddress', 'circuits.circuit', 'circuits.providernetwork',
    'tenancy.tenant', 'netbox_relationships.logicalservice',
)

#: Service map layers, top to bottom.
LAYERS = (
    ('business', 'Business services and applications'),
    ('workload', 'Workloads'),
    ('compute', 'Compute and storage'),
    ('network', 'Network'),
    ('facility', 'Facility'),
)

#: Layer per object type. Devices go to "network" or "compute" by role in
#: servicemap.py; the `layers` setting overrides any of these.
DEFAULT_LAYERS = {
    'netbox_relationships.logicalservice': 'business',
    'virtualization.virtualmachine': 'workload',
    'ipam.service': 'workload',
    'virtualization.cluster': 'compute',
    'dcim.device': 'compute',
    'dcim.virtualchassis': 'network',
    'circuits.circuit': 'network',
    'circuits.providernetwork': 'network',
    'ipam.prefix': 'network',
    'ipam.vlan': 'network',
    'ipam.ipaddress': 'network',
    'dcim.rack': 'facility',
    'dcim.site': 'facility',
    'dcim.location': 'facility',
    'dcim.powerfeed': 'facility',
    'dcim.powerpanel': 'facility',
}

#: Words in a device role's name or slug that put a device on the network
#: layer of the service map instead of compute.
NETWORK_ROLE_WORDS = ('switch', 'router', 'firewall', 'spine', 'leaf', 'gateway', 'network', 'wifi', 'access-point')

#: Relationship types created on a new install (a copy is in migration 0002):
#: (name, slug, forward label, reverse label, category, impact, symmetric, color).
#: Impact is only the default: each relationship can set its own.
DEFAULT_TYPES = (
    ('Depends on', 'depends-on', 'depends on', 'is required by', 'dependency', 'hard', False, '2f6fdf'),
    ('Runs on', 'runs-on', 'runs on', 'hosts', 'hosting', 'hard', False, '6b7690'),
    ('Connects to', 'connects-to', 'connects to', 'connects to', 'connectivity', 'none', True, '9aa3b2'),
    ('Related to', 'related-to', 'is related to', 'is related to', 'informational', 'none', True, 'b0bec5'),
)

#: More types an admin can add with "Add common types" on the types list.
#: Installs from before 0.2.0 already have them; upgrades never remove them.
COMMON_TYPES = (
    ('Sends data to', 'sends-data-to', 'sends data to', 'receives data from', 'data_flow', 'soft', False, '1f7a6b'),
    ('Backed up by', 'backed-up-by', 'is backed up by', 'backs up', 'dependency', 'soft', False, '795548'),
    ('Replicates to', 'replicates-to', 'replicates to', 'is replicated from', 'data_flow', 'soft', False, '00838f'),
    ('Managed by', 'managed-by', 'is managed by', 'manages', 'ownership', 'none', False, '6b4bb8'),
    ('Monitored by', 'monitored-by', 'is monitored by', 'monitors', 'dependency', 'soft', False, '9e9d24'),
    ('Powered by', 'powered-by', 'is powered by', 'powers', 'dependency', 'hard', False, 'e65100'),
    ('Peer of', 'peer-of', 'is a peer of', 'is a peer of', 'informational', 'none', True, '607d8b'),
)
