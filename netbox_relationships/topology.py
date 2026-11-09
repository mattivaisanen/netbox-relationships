"""
Network links worked out from cable paths ("uplinks").

NetBox stores a cable path for each interface: the interface at the far
end, however many patch panels (front and rear ports) sit in between. This
module turns those paths into links between network nodes:

- A node is a device, or its virtual chassis when it is a member of one
  (a stack or a chassis pair acts as one switch).
- Each node gets a tier from its device role (Network Tiers in the UI, or
  the `network_tiers` setting; top of the network first). Devices with other roles are endpoints, below
  the last tier. A circuit sits above every tier.
- Between two nodes, the one in the lower tier "uplinks to" the one in the
  higher tier: a hard dependency. Nodes in the same tier are peers, and
  nodes with no tier "connect to" each other; neither carries impact.
- An `uplink` tag on an interface says "this device needs the far end",
  a `downlink` tag the reverse. Tags win over tiers.
- All uplinks of one node form the redundancy group "uplinks": the node
  keeps working while at least one of them does.
- Several cables between the same two nodes become one link with a count.

Each link is owned by the node that needs the other (or, for peers, the
node with the lower key), so refreshing a node rewrites only the links it
owns. A change anywhere refreshes the nodes at both ends (see watched()).
"""
from collections import defaultdict

from django.apps import apps
from django.contrib.contenttypes.models import ContentType

from . import settings

DEVICE, CHASSIS, CIRCUIT = 'dcim.device', 'dcim.virtualchassis', 'circuits.circuit'

#: Tier given to circuits: above the first configured tier.
CIRCUIT_TIER = -1


def _model(label):
    return apps.get_model(label)


def _ct_id(label):
    app_label, model_name = label.split('.')
    return ContentType.objects.get_by_natural_key(app_label, model_name).pk


def tiers():
    """
    {role slug: tier number}, 0 at the top. Network tiers made in the UI
    win; without any, the `network_tiers` setting is used. Empty when
    neither is set.
    """
    NetworkTier = _model('netbox_relationships.networktier')
    rows = NetworkTier.objects.order_by('level').values_list('level', 'roles__slug')
    if rows.exists():
        levels = sorted({level for level, _slug in rows})
        number = {level: i for i, level in enumerate(levels)}
        return {slug: number[level] for level, slug in rows if slug}
    found = {}
    for number, entry in enumerate(settings.get('network_tiers') or []):
        for slug in ([entry] if isinstance(entry, str) else entry):
            found.setdefault(str(slug), number)
    return found


def tag_slugs():
    """(uplink tag slug, downlink tag slug) for interface overrides."""
    return settings.get('uplink_tag') or 'uplink', settings.get('downlink_tag') or 'downlink'


class Links:
    """
    Links between nodes, read from cable paths. `nodes` is a set of
    (model label, pk) with model DEVICE or CHASSIS.
    """

    def __init__(self, nodes):
        self.nodes = set(nodes)
        self.tier_of_role = tiers()
        self.endpoints = bool(self.tier_of_role) and settings.get('tier_endpoints') is not False

    # -- reading NetBox ------------------------------------------------------

    def _devices(self, nodes):
        """{device pk: (node, role slug)} for every device inside `nodes`."""
        Device = _model(DEVICE)
        device_ids = [pk for label, pk in nodes if label == DEVICE]
        chassis_ids = [pk for label, pk in nodes if label == CHASSIS]
        rows = Device.objects.filter(pk__in=device_ids) | Device.objects.filter(virtual_chassis_id__in=chassis_ids)
        found = {}
        for pk, vc_id, role in rows.values_list('pk', 'virtual_chassis_id', 'role__slug'):
            found[pk] = ((CHASSIS, vc_id) if vc_id else (DEVICE, pk), role)
        return found

    def _far_ends(self, interface_paths):
        """{path pk: [(content type id, pk), ...]} of complete paths' far ends."""
        CablePath = _model('dcim.cablepath')
        far = {}
        rows = CablePath.objects.filter(pk__in=set(interface_paths.values()), is_complete=True)
        for pk, path in rows.values_list('pk', 'path'):
            ends = []
            for node in path[-1] if path else []:
                ct_id, obj_id = node.split(':')
                ends.append((int(ct_id), int(obj_id)))
            far[pk] = ends
        return far

    def collect(self):
        """
        {(near node, far node): {'count', 'near_up', 'near_down', 'far_up',
        'far_down', 'roles'}} for every cabled neighbour of self.nodes.
        """
        Interface = _model('dcim.interface')
        CircuitTermination = _model('circuits.circuittermination')
        interface_ct, circuit_term_ct = _ct_id('dcim.interface'), _ct_id('circuits.circuittermination')
        up_tag, down_tag = tag_slugs()

        mine = self._devices(self.nodes)
        # Management-only (out-of-band) ports never make uplinks, at either end.
        rows = Interface.objects.filter(device_id__in=mine, _path__isnull=False, mgmt_only=False)
        near = {pk: (device_id, path_id) for pk, device_id, path_id in rows.values_list('pk', 'device_id', '_path_id')}
        far_ends = self._far_ends({pk: path_id for pk, (_, path_id) in near.items()})

        # Far interfaces and circuit terminations, resolved to nodes.
        far_interfaces = {pk for ends in far_ends.values() for ct, pk in ends if ct == interface_ct}
        far_terms = {pk for ends in far_ends.values() for ct, pk in ends if ct == circuit_term_ct}
        far_device_of = dict(
            Interface.objects.filter(pk__in=far_interfaces, mgmt_only=False).values_list('pk', 'device_id'))
        circuit_of = dict(CircuitTermination.objects.filter(pk__in=far_terms).values_list('pk', 'circuit_id'))
        theirs = self._devices({(DEVICE, pk) for pk in far_device_of.values()})

        tagged = defaultdict(set)
        for pk, slug in Interface.objects.filter(
                pk__in=set(near) | far_interfaces, tags__slug__in=(up_tag, down_tag)).values_list('pk', 'tags__slug'):
            tagged[pk].add(slug)

        self.roles = {node: role for node, role in list(mine.values()) + list(theirs.values())}
        # A chassis takes the highest tier any member has.
        for node, role in list(mine.values()) + list(theirs.values()):
            if node[0] == CHASSIS:
                current = self.roles.get(node)
                if self._tier_of(role) is not None and (
                        self._tier_of(current) is None or self._tier_of(role) < self._tier_of(current)):
                    self.roles[node] = role

        links = {}
        for interface_id, (device_id, path_id) in near.items():
            node = mine[device_id][0]
            for ct, pk in far_ends.get(path_id, ()):
                if ct == interface_ct and pk in far_device_of:
                    other = theirs[far_device_of[pk]][0]
                elif ct == circuit_term_ct and pk in circuit_of:
                    other = (CIRCUIT, circuit_of[pk])
                else:
                    continue
                if other == node:
                    continue  # a cable between two members of one stack
                link = links.setdefault((node, other), {
                    'count': 0, 'near_up': False, 'near_down': False, 'far_up': False, 'far_down': False,
                })
                link['count'] += 1
                link['near_up'] |= up_tag in tagged[interface_id]
                link['near_down'] |= down_tag in tagged[interface_id]
                link['far_up'] |= ct == interface_ct and up_tag in tagged[pk]
                link['far_down'] |= ct == interface_ct and down_tag in tagged[pk]
        return links

    # -- deciding direction --------------------------------------------------

    def _tier_of(self, role):
        if role is None:
            return None
        if role in self.tier_of_role:
            return self.tier_of_role[role]
        return len(self.tier_of_role) if self.endpoints else None

    def tier(self, node):
        if node[0] == CIRCUIT:
            return CIRCUIT_TIER if self.tier_of_role else None
        return self._tier_of(self.roles.get(node))

    def direction(self, node, other, link):
        """
        'needs' (node needs other), 'needed' (other needs node), 'peer' (same
        tier) or 'connects' (no tier known).
        """
        if link['near_up'] or link['far_down']:
            return 'needs'
        if link['near_down'] or link['far_up']:
            return 'needed'
        mine, theirs = self.tier(node), self.tier(other)
        if mine is None or theirs is None:
            return 'connects'
        if mine == theirs:
            return 'peer'
        return 'needs' if mine > theirs else 'needed'


def node_key(node):
    """Sort key for a node, so exactly one end owns a peer link."""
    return _ct_id(node[0]), node[1]


def nodes_of_devices(device_ids):
    """The nodes (device or its chassis) the devices belong to."""
    Device = _model(DEVICE)
    nodes = set()
    for pk, vc_id in Device.objects.filter(pk__in=device_ids).values_list('pk', 'virtual_chassis_id'):
        nodes.add((CHASSIS, vc_id) if vc_id else (DEVICE, pk))
    return nodes


def neighbours(nodes):
    """Nodes cabled to any of `nodes` (devices and chassis only)."""
    return {other for (_node, other) in Links(nodes).collect() if other[0] != CIRCUIT}


