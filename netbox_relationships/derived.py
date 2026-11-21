"""
Links NetBox already knows, worked out from its own data ("edge providers").

Each provider reads one NetBox model (its owner) and returns edges. An edge
always reads source -> target as "source needs target": a VM runs on its
cluster, so a failed cluster takes the VM down. The provider also says how
to refresh: which saved or deleted objects change which owners' edges
(see signals.py), so a change rewrites only the rows it touches.

Each edge has an EdgeSpec: its settings key (PLUGINS_CONFIG 'derived'),
labels, impact and colour. One provider can produce more than one kind:
network cables give "uplinks to", "is a peer of" or "connects to"
(topology.py decides which).
"""
from collections import namedtuple

from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import ngettext

from . import topology
from .choices import ImpactChoices

EdgeSpec = namedtuple('EdgeSpec', 'key label reverse_label impact symmetric color')

#: (owner pk, source model, source pk, target model, target pk, spec), plus
#: optional redundancy group (edges from one source with the same group back
#: each other up; the source needs `group_min` of them), the number of
#: physical links folded into the edge, and a note on where it comes from.
Edge = namedtuple(
    'Edge', 'owner_id source_model source_id target_model target_id spec group group_min link_count note',
    defaults=('', 1, 1, ''),
)

VM_RUNS_ON = EdgeSpec('vm_cluster', 'runs on', 'hosts', ImpactChoices.HARD, False, '6b7690')
CLUSTER_ON_HOST = EdgeSpec('cluster_hosts', 'runs on', 'hosts', ImpactChoices.HARD, False, '6b7690')
SERVICE_ON = EdgeSpec('service_parent', 'runs on', 'hosts', ImpactChoices.HARD, False, '1f7a6b')
CONNECTS = EdgeSpec('cables', 'connects to', 'connects to', ImpactChoices.NONE, True, '9aa3b2')
UPLINK = EdgeSpec('cables', 'uplinks to', 'is the uplink of', ImpactChoices.HARD, False, '3b82c4')
PEER = EdgeSpec('cables', 'is a peer of', 'is a peer of', ImpactChoices.NONE, True, '607d8b')
POWERED_BY = EdgeSpec('power', 'is powered by', 'powers', ImpactChoices.HARD, False, 'e65100')
FED_BY = EdgeSpec('power', 'is fed by', 'feeds', ImpactChoices.HARD, False, 'e65100')
TERMINATES = EdgeSpec('circuits', 'terminates at', 'is a termination of', ImpactChoices.NONE, False, '9aa3b2')
VC_RUNS_ON = EdgeSpec('virtual_chassis', 'runs on', 'is a member of', ImpactChoices.HARD, False, '607d8b')
CONSISTS_OF = EdgeSpec('logical_parent', 'consists of', 'is part of', ImpactChoices.HARD, False, '6b4bb8')
LOCATED_IN = EdgeSpec('placement', 'is located in', 'contains', ImpactChoices.NONE, False, 'b0bec5')
IN_PREFIX = EdgeSpec('ip_prefix', 'is in', 'contains', ImpactChoices.NONE, False, 'b0bec5')
IN_VLAN = EdgeSpec('ip_prefix', 'is on', 'carries', ImpactChoices.NONE, False, 'b0bec5')


def model(label):
    return apps.get_model(label)


class Provider:
    """Base class: one owner model, edges built for a set of owners."""
    #: The model whose objects own the edges ('virtualization.virtualmachine').
    owner = None
    #: Specs this provider can produce.
    specs = ()

    @property
    def keys(self):
        return {spec.key for spec in self.specs}

    def watched(self):
        """
        [(model label, function)]: saving or deleting an object of that model
        refreshes the owners the function returns for it (a list of pks).
        """
        return [(self.owner, lambda obj: [obj.pk])]

    def owners(self, ids=None):
        queryset = model(self.owner).objects.all()
        return queryset if ids is None else queryset.filter(pk__in=ids)

    def build(self, ids=None):
        """Edges of the owners with these pks (all owners when None)."""
        raise NotImplementedError


class VMProvider(Provider):
    """A VM runs on its cluster, and on its device when pinned to one."""
    owner = 'virtualization.virtualmachine'
    specs = (VM_RUNS_ON,)

    def build(self, ids=None):
        vm, cluster, device = 'virtualization.virtualmachine', 'virtualization.cluster', 'dcim.device'
        for pk, cluster_id, device_id in self.owners(ids).values_list('pk', 'cluster_id', 'device_id'):
            if cluster_id:
                yield Edge(pk, vm, pk, cluster, cluster_id, VM_RUNS_ON)
            if device_id:
                yield Edge(pk, vm, pk, device, device_id, VM_RUNS_ON)


class ClusterHostProvider(Provider):
    """
    A cluster runs on each of its devices. The hosts form one redundancy
    group: losing one leaves the cluster at risk, losing all takes it down.
    """
    owner = 'dcim.device'
    specs = (CLUSTER_ON_HOST,)

    def build(self, ids=None):
        for pk, cluster_id in self.owners(ids).filter(cluster__isnull=False).values_list('pk', 'cluster_id'):
            yield Edge(pk, 'virtualization.cluster', cluster_id, 'dcim.device', pk, CLUSTER_ON_HOST, group='hosts')


class ServiceProvider(Provider):
    """A service (port) runs on its device, VM or FHRP group."""
    owner = 'ipam.service'
    specs = (SERVICE_ON,)

    def build(self, ids=None):
        rows = self.owners(ids).values_list('pk', 'parent_object_type_id', 'parent_object_id')
        for pk, parent_type_id, parent_id in rows:
            parent_model = ContentType.objects.get_for_id(parent_type_id).model_class()
            if parent_model is not None:
                yield Edge(pk, 'ipam.service', pk, parent_model._meta.label_lower, parent_id, SERVICE_ON)


_POWER_PORT, _POWER_OUTLET, _POWER_FEED = 'powerport', 'poweroutlet', 'powerfeed'


class PowerCableProvider(Provider):
    """
    Power cables: the device with the power port is powered by the device
    with the outlet (a PDU) or by the power feed. All power supplies of one
    device form the redundancy group "power". Network cables are handled by
    the uplink providers below.
    """
    owner = 'dcim.cable'
    specs = (POWERED_BY,)

    def watched(self):
        # Terminations are saved after their cable, so they trigger the refresh.
        return [
            (self.owner, lambda obj: [obj.pk]),
            ('dcim.cabletermination', lambda obj: [obj.cable_id]),
        ]

    def build(self, ids=None):
        CableTermination = model('dcim.cabletermination')
        rows = CableTermination.objects.all()
        if ids is not None:
            rows = rows.filter(cable_id__in=ids)
        ends = {}
        for cable_id, end, type_id, term_id, device_id in rows.values_list(
                'cable_id', 'cable_end', 'termination_type_id', 'termination_id', '_device_id'):
            kind = ContentType.objects.get_for_id(type_id).model
            ends.setdefault(cable_id, {'A': [], 'B': []})[end].append((kind, term_id, device_id))

        def node(kind, term_id, device_id):
            """(model label, pk) of what a cable end belongs to, or None."""
            if kind == _POWER_FEED:
                return 'dcim.powerfeed', term_id
            return ('dcim.device', device_id) if device_id else None

        for cable_id, sides in ends.items():
            seen = set()
            for a in sides['A']:
                for b in sides['B']:
                    kinds = {a[0], b[0]}
                    if _POWER_PORT not in kinds or not kinds & {_POWER_OUTLET, _POWER_FEED}:
                        continue
                    port, supply = (a, b) if a[0] == _POWER_PORT else (b, a)
                    src, tgt = node(*port), node(*supply)
                    if not src or not tgt or src == tgt or (src, tgt) in seen:
                        continue
                    seen.add((src, tgt))
                    yield Edge(cable_id, src[0], src[1], tgt[0], tgt[1], POWERED_BY, group='power')


class PowerFeedProvider(Provider):
    """A power feed is fed by its power panel."""
    owner = 'dcim.powerfeed'
    specs = (FED_BY,)

    def build(self, ids=None):
        for pk, panel_id in self.owners(ids).values_list('pk', 'power_panel_id'):
            yield Edge(pk, 'dcim.powerfeed', pk, 'dcim.powerpanel', panel_id, FED_BY)


class CircuitProvider(Provider):
    """A circuit terminates at a site, location, region or provider network."""
    owner = 'circuits.circuittermination'
    specs = (TERMINATES,)

    def build(self, ids=None):
        rows = self.owners(ids).filter(termination_type__isnull=False)
        for pk, circuit_id, type_id, term_id in rows.values_list(
                'pk', 'circuit_id', 'termination_type_id', 'termination_id'):
            target = ContentType.objects.get_for_id(type_id).model_class()
            if target is not None and term_id:
                yield Edge(pk, 'circuits.circuit', circuit_id, target._meta.label_lower, term_id, TERMINATES)


class VirtualChassisProvider(Provider):
    """
    A virtual chassis (a stack, or a pair of switches acting as one) runs on
    its members. The members form one redundancy group: losing one leaves
    the chassis at risk, losing all takes it down.
    """
    owner = 'dcim.device'
    specs = (VC_RUNS_ON,)

    def build(self, ids=None):
        rows = self.owners(ids).filter(virtual_chassis__isnull=False).values_list('pk', 'virtual_chassis_id')
        for pk, vc_id in rows:
            yield Edge(pk, 'dcim.virtualchassis', vc_id, 'dcim.device', pk, VC_RUNS_ON, group='members')


class _UplinkProvider(Provider):
    """
    Network cables, read as whole cable paths (through patch panels) and
    turned into uplinks, peer links or plain connections by topology.py.
    Two providers share this code: one owns the links of devices that are
    not in a virtual chassis, the other the links of virtual chassis.
    """
    specs = (UPLINK, PEER, CONNECTS)
    #: topology node label this provider owns (DEVICE or CHASSIS).
    node_label = None

    def _ids(self, nodes):
        return [pk for label, pk in nodes if label == self.node_label]

    def _with_neighbours(self, nodes):
        nodes = set(nodes)
        return self._ids(nodes | topology.neighbours(nodes))

    def watched(self):
        def from_path(path):
            # Both ends of a cable path: the interfaces' devices.
            interface_ct = ContentType.objects.get_for_model(model('dcim.interface')).pk
            interface_ids = []
            for step in (path.path[:1] + path.path[-1:]) if path.path else ():
                for node in step:
                    ct_id, pk = node.split(':')
                    if int(ct_id) == interface_ct:
                        interface_ids.append(int(pk))
            interfaces = model('dcim.interface').objects.filter(pk__in=interface_ids)
            device_ids = interfaces.values_list('device_id', flat=True)
            return self._ids(topology.nodes_of_devices(device_ids))

        def from_device(device):
            # A role or chassis change can turn links of the neighbours around.
            nodes = {(topology.DEVICE, device.pk)}
            if device.virtual_chassis_id:
                nodes.add((topology.CHASSIS, device.virtual_chassis_id))
            return self._with_neighbours(nodes)

        def from_tag(item):
            # An uplink/downlink tag added to or removed from an interface.
            interface = model('dcim.interface')
            if item.content_type_id != ContentType.objects.get_for_model(interface).pk:
                return []
            device_ids = interface.objects.filter(pk=item.object_id).values_list('device_id', flat=True)
            return self._with_neighbours(topology.nodes_of_devices(device_ids))

        return [('dcim.cablepath', from_path), ('dcim.device', from_device), ('extras.taggeditem', from_tag)]

    def build(self, ids=None):
        if ids is None:
            ids = self.owners().values_list('pk', flat=True)
        nodes = {(self.node_label, pk) for pk in ids}
        links = topology.Links(nodes)
        for (node, other), link in links.collect().items():
            if node[0] != self.node_label:
                continue
            direction = links.direction(node, other, link)
            count = link['count']
            note = ngettext('%(n)d cable', '%(n)d cables', count) % {'n': count}
            if direction == 'needs':
                yield Edge(node[1], node[0], node[1], other[0], other[1], UPLINK,
                           group='uplinks', link_count=count, note=note)
            elif other[0] == topology.CIRCUIT:
                # A circuit owns nothing, so this end keeps every circuit link.
                spec = UPLINK if direction == 'needed' else CONNECTS
                if spec is UPLINK:
                    yield Edge(node[1], other[0], other[1], node[0], node[1], spec, link_count=count, note=note)
                else:
                    yield Edge(node[1], node[0], node[1], other[0], other[1], spec, link_count=count, note=note)
            elif direction in ('peer', 'connects') and topology.node_key(node) < topology.node_key(other):
                spec = PEER if direction == 'peer' else CONNECTS
                yield Edge(node[1], node[0], node[1], other[0], other[1], spec, link_count=count, note=note)
            # 'needed': the other end owns that link.


class DeviceUplinkProvider(_UplinkProvider):
    """Network links of devices that are not in a virtual chassis."""
    owner = 'dcim.device'
    node_label = topology.DEVICE

    def owners(self, ids=None):
        return super().owners(ids).filter(virtual_chassis__isnull=True)


class ChassisUplinkProvider(_UplinkProvider):
    """Network links of virtual chassis (stacks and switch pairs), from all their members' cables."""
    owner = 'dcim.virtualchassis'
    node_label = topology.CHASSIS


class LogicalParentProvider(Provider):
    """A business service (or application) consists of the services inside it."""
    owner = 'netbox_relationships.logicalservice'
    specs = (CONSISTS_OF,)

    def build(self, ids=None):
        label = self.owner
        for pk, parent_id in self.owners(ids).filter(parent__isnull=False).values_list('pk', 'parent_id'):
            yield Edge(pk, label, parent_id, label, pk, CONSISTS_OF)


class PlacementProvider(Provider):
    """A device sits in its rack, or else its location, or else its site."""
    owner = 'dcim.device'
    specs = (LOCATED_IN,)

    def build(self, ids=None):
        for pk, rack_id, location_id, site_id in self.owners(ids).values_list(
                'pk', 'rack_id', 'location_id', 'site_id'):
            if rack_id:
                yield Edge(pk, 'dcim.device', pk, 'dcim.rack', rack_id, LOCATED_IN)
            elif location_id:
                yield Edge(pk, 'dcim.device', pk, 'dcim.location', location_id, LOCATED_IN)
            elif site_id:
                yield Edge(pk, 'dcim.device', pk, 'dcim.site', site_id, LOCATED_IN)


class PrefixVLANProvider(Provider):
    """A prefix is on its VLAN."""
    owner = 'ipam.prefix'
    specs = (IN_VLAN,)

    def build(self, ids=None):
        for pk, vlan_id in self.owners(ids).filter(vlan__isnull=False).values_list('pk', 'vlan_id'):
            yield Edge(pk, 'ipam.prefix', pk, 'ipam.vlan', vlan_id, IN_VLAN)


class IPPrefixProvider(Provider):
    """
    An IP address is in the most specific prefix (same VRF) that contains it.
    Refreshed when the address is saved; a new or changed prefix is picked
    up by the nightly rebuild.
    """
    owner = 'ipam.ipaddress'
    specs = (IN_PREFIX,)

    def build(self, ids=None):
        Prefix = model('ipam.prefix')
        for ip in self.owners(ids).only('pk', 'address', 'vrf_id'):
            prefix_id = Prefix.objects.filter(
                vrf_id=ip.vrf_id, prefix__net_contains_or_equals=str(ip.address.ip),
            ).order_by('-_depth').values_list('pk', flat=True).first()
            if prefix_id:
                yield Edge(ip.pk, 'ipam.ipaddress', ip.pk, 'ipam.prefix', prefix_id, IN_PREFIX)


#: The providers that read network cables (rerun when the tiers change).
UPLINK_PROVIDERS = (DeviceUplinkProvider(), ChassisUplinkProvider())

#: Every provider, in the order a rebuild runs them.
PROVIDERS = (
    VMProvider(), ClusterHostProvider(), ServiceProvider(), PowerCableProvider(), PowerFeedProvider(),
    CircuitProvider(), VirtualChassisProvider(), *UPLINK_PROVIDERS,
    LogicalParentProvider(), PlacementProvider(), PrefixVLANProvider(), IPPrefixProvider(),
)
