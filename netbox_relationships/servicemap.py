"""
The layered service map: logical services at the top, then what they stand
on, one band per layer (constants.LAYERS). Read only.

The map starts from logical services (all of them, or one and its
children), walks "down" to everything they need, and puts each object in
the band of its type. Applications are drawn inside their business service.
"""
from django.contrib.contenttypes.models import ContentType

from . import settings
from .constants import DEFAULT_LAYERS, LAYERS, NETWORK_ROLE_WORDS
from .graph import DOWN, Filters, resolve, walk
from .models import LogicalService


def layer_of(obj):
    label = type(obj)._meta.label_lower
    layer = (settings.get('layers') or {}).get(label) or DEFAULT_LAYERS.get(label, 'compute')
    if label == 'dcim.device' and label not in (settings.get('layers') or {}):
        role = getattr(obj, 'role', None)
        text = f'{getattr(role, "name", "")} {getattr(role, "slug", "")}'.lower()
        if any(word in text for word in NETWORK_ROLE_WORDS):
            layer = 'network'
    return layer


def build(user, service=None, states=None):
    """
    {'business': [...], 'layers': [(key, title, [node, ...])], 'truncated'}.
    `states` ({(ct, pk): state} from impact analysis) colours the nodes.
    """
    states = states or {}
    services = LogicalService.objects.restrict(user, 'view')
    if service is not None:
        ids = {service.pk} | set(service.children.values_list('pk', flat=True))
        services = services.filter(pk__in=ids)
    ct = ContentType.objects.get_for_model(LogicalService)
    roots = {(ct.pk, pk) for pk in services.values_list('pk', flat=True)}
    hops, _edges, truncated = walk(
        roots, DOWN, int(settings.get('max_depth')), Filters(), int(settings.get('max_nodes')),
    )
    nodes = resolve(user, hops)
    for node_id, node in nodes.items():
        node['state'] = states.get(node_id)

    # Business band: business services with their applications inside,
    # then logical services that belong to none.
    service_nodes = {
        node['object'].pk: node for node in nodes.values()
        if not node['hidden'] and type(node['object']) is LogicalService
    }
    business, loose = [], []
    for pk, node in sorted(service_nodes.items(), key=lambda item: item[1]['label']):
        obj = node['object']
        if obj.parent_id and obj.parent_id in service_nodes:
            continue
        children = [
            service_nodes[child] for child in sorted(service_nodes, key=lambda c: service_nodes[c]['label'])
            if service_nodes[child]['object'].parent_id == pk
        ]
        (business if children or obj.kind == 'business_service' else loose).append(
            {'node': node, 'children': children},
        )
    business.extend(loose)

    bands = {layer: [] for layer, _title in LAYERS}
    for node in nodes.values():
        obj = node.get('object')
        if obj is not None and type(obj) is LogicalService:
            continue
        layer = layer_of(obj) if obj is not None else 'compute'
        bands.setdefault(layer, []).append(node)
    layers = [
        (layer, title, sorted(bands.get(layer, []), key=lambda n: (n['kind'], n['label'])))
        for layer, title in LAYERS if layer != 'business'
    ]
    return {'business': business, 'layers': layers, 'truncated': truncated}
