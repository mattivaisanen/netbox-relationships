"""
Links NetBox already knows, worked out from its own data ("edge providers").

Each provider reads one NetBox model (its owner) and returns edges. An edge
always reads source -> target as "source needs target": a VM runs on its
cluster, so a failed cluster takes the VM down. The provider also says how
to refresh: which saved or deleted objects change which owners' edges
(see signals.py), so a change rewrites only the rows it touches.

Each edge has an EdgeSpec: its settings key (PLUGINS_CONFIG 'derived'),
labels, impact and colour. One provider can produce more than one kind:
cables give "connects to" for network cables and "powered by" for power.
"""
from collections import namedtuple

from django.apps import apps
from django.contrib.contenttypes.models import ContentType

from .choices import ImpactChoices

EdgeSpec = namedtuple('EdgeSpec', 'key label reverse_label impact symmetric color')

#: (owner pk, source model, source pk, target model, target pk, spec)
Edge = namedtuple('Edge', 'owner_id source_model source_id target_model target_id spec')

VM_RUNS_ON = EdgeSpec('vm_cluster', 'runs on', 'hosts', ImpactChoices.HARD, False, '6b7690')
CLUSTER_ON_HOST = EdgeSpec('cluster_hosts', 'runs on', 'hosts', ImpactChoices.SOFT, False, '6b7690')
SERVICE_ON = EdgeSpec('service_parent', 'runs on', 'hosts', ImpactChoices.HARD, False, '1f7a6b')
CONNECTS = EdgeSpec('cables', 'connects to', 'connects to', ImpactChoices.NONE, True, '9aa3b2')
POWERED_BY = EdgeSpec('power', 'is powered by', 'powers', ImpactChoices.HARD, False, 'e65100')
FED_BY = EdgeSpec('power', 'is fed by', 'feeds', ImpactChoices.HARD, False, 'e65100')
TERMINATES = EdgeSpec('circuits', 'terminates at', 'is a termination of', ImpactChoices.NONE, False, '9aa3b2')
VC_MEMBER = EdgeSpec('virtual_chassis', 'is a member of', 'has member', ImpactChoices.NONE, False, '607d8b')
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
    A cluster runs on each of its devices. Soft: losing one host degrades
    the cluster, it doesn't take it down.
    """
    owner = 'dcim.device'
    specs = (CLUSTER_ON_HOST,)

    def build(self, ids=None):
        for pk, cluster_id in self.owners(ids).filter(cluster__isnull=False).values_list('pk', 'cluster_id'):
            yield Edge(pk, 'virtualization.cluster', cluster_id, 'dcim.device', pk, CLUSTER_ON_HOST)


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


#: Cable ends that carry network traffic, and those that carry power.
_NETWORK_ENDS = {'interface', 'frontport', 'rearport', 'circuittermination'}
_POWER_PORT, _POWER_OUTLET, _POWER_FEED = 'powerport', 'poweroutlet', 'powerfeed'


class CableProvider(Provider):
    """
    Network cables: the devices (or circuit) at the two ends connect to
    each other, with no impact either way since a cable has no direction.

    Power cables: the device with the power port is powered by the device
    with the outlet (a PDU) or by the power feed.
    """
    owner = 'dcim.cable'
    specs = (CONNECTS, POWERED_BY)

    def watched(self):
        # Terminations are saved after their cable, so they trigger the refresh.
        return [
            (self.owner, lambda obj: [obj.pk]),
            ('dcim.cabletermination', lambda obj: [obj.cable_id]),
        ]

    def build(self, ids=None):
        CableTermination = model('dcim.cabletermination')
        CircuitTermination = model('circuits.circuittermination')
        rows = CableTermination.objects.all()
        if ids is not None:
            rows = rows.filter(cable_id__in=ids)
        ends = {}
        circuit_terms = set()
        for cable_id, end, type_id, term_id, device_id in rows.values_list(
                'cable_id', 'cable_end', 'termination_type_id', 'termination_id', '_device_id'):
            kind = ContentType.objects.get_for_id(type_id).model
            if kind == 'circuittermination':
                circuit_terms.add(term_id)
            ends.setdefault(cable_id, {'A': [], 'B': []})[end].append((kind, term_id, device_id))
        circuits = dict(CircuitTermination.objects.filter(pk__in=circuit_terms).values_list('pk', 'circuit_id'))

        def node(kind, term_id, device_id):
            """(model label, pk) of what a cable end belongs to, or None."""
            if kind == 'circuittermination':
                circuit_id = circuits.get(term_id)
                return ('circuits.circuit', circuit_id) if circuit_id else None
            if kind == _POWER_FEED:
                return 'dcim.powerfeed', term_id
            return ('dcim.device', device_id) if device_id else None

        for cable_id, sides in ends.items():
            seen = set()
            for a in sides['A']:
                for b in sides['B']:
                    edge = self._pair(a, b, node)
                    if edge is None:
                        continue
                    (src, tgt, spec) = edge
                    if src == tgt or (src, tgt, spec.key) in seen:
                        continue
                    seen.add((src, tgt, spec.key))
                    yield Edge(cable_id, src[0], src[1], tgt[0], tgt[1], spec)

    @staticmethod
    def _pair(a, b, node):
        """(source node, target node, spec) for two cable ends, or None."""
        kinds = {a[0], b[0]}
        if _POWER_PORT in kinds and kinds & {_POWER_OUTLET, _POWER_FEED}:
            port, supply = (a, b) if a[0] == _POWER_PORT else (b, a)
            src, tgt = node(*port), node(*supply)
            return (src, tgt, POWERED_BY) if src and tgt else None
        if a[0] in _NETWORK_ENDS and b[0] in _NETWORK_ENDS:
            src, tgt = node(*a), node(*b)
            return (src, tgt, CONNECTS) if src and tgt else None
        return None


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
    """A device is a member of its virtual chassis."""
    owner = 'dcim.device'
    specs = (VC_MEMBER,)

    def build(self, ids=None):
        rows = self.owners(ids).filter(virtual_chassis__isnull=False).values_list('pk', 'virtual_chassis_id')
        for pk, vc_id in rows:
            yield Edge(pk, 'dcim.device', pk, 'dcim.virtualchassis', vc_id, VC_MEMBER)


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


#: Every provider, in the order a rebuild runs them.
PROVIDERS = (
    VMProvider(), ClusterHostProvider(), ServiceProvider(), CableProvider(), PowerFeedProvider(),
    CircuitProvider(), VirtualChassisProvider(), LogicalParentProvider(), PlacementProvider(),
    PrefixVLANProvider(), IPPrefixProvider(),
)
