"""
Walks the edge index around one or more objects and returns a graph
(nodes and edges) that a user may see. Read only.

An edge always reads source -> target as "source needs target":

- walking "down" follows source -> target: what an object needs;
- walking "up" follows target -> source: what needs the object.

Symmetric edges (peers, cables) are followed both ways in both walks.
Each hop costs one query per direction, however many objects the frontier
holds, so a graph of a few thousand objects stays a handful of queries.
"""
from collections import defaultdict

from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.utils.translation import gettext as _

from . import settings
from .choices import ServiceKindChoices
from .constants import MANUAL
from .models import EdgeIndex

DOWN, UP, BOTH = 'down', 'up', 'both'

EDGE_FIELDS = (
    'pk', 'source_type_id', 'source_id', 'target_type_id', 'target_id', 'origin', 'relationship_id',
    'rtype_id', 'label', 'reverse_label', 'impact', 'symmetric', 'status', 'criticality', 'color',
)


def key(ct_id, pk):
    """A node's id in graphs and the API: "<content type id>:<pk>"."""
    return f'{ct_id}:{pk}'


def parse_key(value):
    """(content type id, pk) from "12:34" or "dcim.device:34", or None."""
    try:
        type_part, pk = str(value).rsplit(':', 1)
        pk = int(pk)
        if '.' in type_part:
            app_label, model_name = type_part.lower().split('.', 1)
            ct = ContentType.objects.get_by_natural_key(app_label, model_name)
            return ct.pk, pk
        return int(type_part), pk
    except (ValueError, ContentType.DoesNotExist):
        return None


def object_key(obj):
    return key(ContentType.objects.get_for_model(obj).pk, obj.pk)


class Filters:
    """What a walk may follow."""

    def __init__(self, derived=True, statuses=None, rtypes=None, impacting_only=False):
        self.derived = derived
        self.statuses = statuses
        self.rtypes = rtypes
        self.impacting_only = impacting_only

    def apply(self, queryset):
        if not self.derived:
            queryset = queryset.filter(origin=MANUAL)
        if self.statuses:
            queryset = queryset.filter(status__in=self.statuses)
        if self.rtypes:
            queryset = queryset.filter(Q(rtype_id__in=self.rtypes) | ~Q(origin=MANUAL))
        if self.impacting_only:
            queryset = queryset.exclude(impact='none')
        return queryset


def _frontier_q(frontier, side):
    """Q matching edges whose `side` ('source' or 'target') is in the frontier."""
    by_type = defaultdict(list)
    for ct_id, pk in frontier:
        by_type[ct_id].append(pk)
    q = Q()
    for ct_id, pks in by_type.items():
        q |= Q(**{f'{side}_type_id': ct_id, f'{side}_id__in': pks})
    return q


def edges_from(frontier, direction, filters):
    """
    Edge rows (dicts) leaving the frontier in `direction`, each with
    'next': the (ct, pk) at the far end.
    """
    if not frontier:
        return []
    near, far = ('source', 'target') if direction == DOWN else ('target', 'source')
    queryset = filters.apply(EdgeIndex.objects.all())
    query = _frontier_q(frontier, near) | (Q(symmetric=True) & _frontier_q(frontier, far))
    rows = []
    for row in queryset.filter(query).values(*EDGE_FIELDS):
        src, tgt = (row['source_type_id'], row['source_id']), (row['target_type_id'], row['target_id'])
        # A symmetric edge reached from its far end leads to its near end.
        if direction == DOWN:
            row['next'] = tgt if src in frontier else src
        else:
            row['next'] = src if tgt in frontier else tgt
        rows.append(row)
    return rows


def walk(roots, direction, depth, filters, max_nodes):
    """
    Breadth-first from `roots` (a set of (ct, pk)). Returns
    ({node: hops}, {edge pk: row}, truncated).
    """
    hops = {root: 0 for root in roots}
    edges = {}
    frontier = set(roots)
    truncated = False
    for level in range(1, depth + 1):
        found = set()
        for row in edges_from(frontier, direction, filters):
            edges[row['pk']] = row
            nxt = row['next']
            if nxt not in hops:
                if len(hops) >= max_nodes:
                    truncated = True
                    continue
                hops[nxt] = level
                found.add(nxt)
        frontier = found
        if not frontier:
            break
    # Keep only edges between collected nodes (a cut-off can strand some).
    edges = {
        pk: row for pk, row in edges.items()
        if (row['source_type_id'], row['source_id']) in hops and (row['target_type_id'], row['target_id']) in hops
    }
    return hops, edges, truncated


def _node_group(obj, model):
    """The colour group of a node in the graph."""
    label = model._meta.label_lower
    if label == 'netbox_relationships.logicalservice':
        return {
            ServiceKindChoices.BUSINESS_SERVICE: 'business',
            ServiceKindChoices.EXTERNAL: 'external',
        }.get(obj.kind, 'application')
    return {
        'virtualization.virtualmachine': 'vm',
        'virtualization.cluster': 'cluster',
        'ipam.service': 'service',
        'dcim.device': 'device',
        'circuits.circuit': 'circuit',
        'dcim.powerfeed': 'power',
        'dcim.powerpanel': 'power',
    }.get(label, 'other')


def _status(obj):
    status = getattr(obj, 'status', None)
    if status is None:
        return None, None
    value = status if isinstance(status, str) else getattr(status, 'value', None)
    color = obj.get_status_color() if hasattr(obj, 'get_status_color') else None
    label = obj.get_status_display() if hasattr(obj, 'get_status_display') else value
    return label, color


def resolve(user, node_ids):
    """
    {(ct, pk): node dict} for the objects behind `node_ids`, with what the
    user may see. Objects the user can't view become hidden placeholders;
    their names never leave the server.
    """
    by_type = defaultdict(list)
    for ct_id, pk in node_ids:
        by_type[ct_id].append(pk)
    nodes = {}
    for ct_id, pks in by_type.items():
        model = ContentType.objects.get_for_id(ct_id).model_class()
        visible = {}
        if model is not None:
            queryset = model.objects.all()
            if hasattr(queryset, 'restrict'):
                queryset = queryset.restrict(user, 'view')
            visible = {obj.pk: obj for obj in queryset.filter(pk__in=pks)}
        for pk in pks:
            obj = visible.get(pk)
            if obj is None:
                nodes[(ct_id, pk)] = {
                    'id': key(ct_id, pk), 'label': _('Hidden object'), 'kind': '', 'group': 'hidden',
                    'url': None, 'status': None, 'status_color': None, 'hidden': True,
                }
                continue
            status, status_color = _status(obj)
            kind = obj.get_kind_display() if hasattr(obj, 'get_kind_display') else model._meta.verbose_name
            try:
                url = obj.get_absolute_url()
            except Exception:
                url = None
            nodes[(ct_id, pk)] = {
                'id': key(ct_id, pk), 'label': str(obj), 'kind': str(kind)[:1].upper() + str(kind)[1:],
                'group': _node_group(obj, model), 'url': url, 'status': status, 'status_color': status_color,
                'hidden': False, 'object': obj,
            }
    return nodes


def edge_dict(row):
    return {
        'id': f"e{row['pk']}",
        'source': key(row['source_type_id'], row['source_id']),
        'target': key(row['target_type_id'], row['target_id']),
        'label': row['label'],
        'reverse_label': row['reverse_label'],
        'origin': 'manual' if row['origin'] == MANUAL else 'netbox',
        'kind': row['origin'],
        'relationship': row['relationship_id'],
        'impact': row['impact'],
        'symmetric': row['symmetric'],
        'status': row['status'],
        'criticality': row['criticality'],
        'color': row['color'],
    }


def build(user, roots, direction=BOTH, depth=None, filters=None):
    """
    The graph around `roots` (iterable of (ct, pk)) as a JSON-ready dict:
    {'nodes': [...], 'edges': [...], 'roots': [...], 'truncated': bool}.
    """
    roots = set(roots)
    depth = settings.depth(depth)
    filters = filters or Filters()
    max_nodes = int(settings.get('max_nodes'))
    hops, edges, truncated = {}, {}, False
    directions = (DOWN, UP) if direction == BOTH else (direction,)
    for each in directions:
        found, found_edges, cut = walk(roots, each, depth, filters, max_nodes)
        for node, level in found.items():
            hops[node] = min(level, hops.get(node, level))
        edges.update(found_edges)
        truncated = truncated or cut

    nodes = resolve(user, hops)
    omit = settings.get('hidden_nodes') == 'omit'
    out_nodes = []
    for node_id, node in nodes.items():
        if node['hidden'] and omit and node_id not in roots:
            continue
        node = {k: v for k, v in node.items() if k != 'object'}
        node['hops'] = hops[node_id]
        node['root'] = node_id in roots
        out_nodes.append(node)
    shown = {node['id'] for node in out_nodes}
    out_edges = [edge_dict(row) for row in edges.values()]
    out_edges = [edge for edge in out_edges if edge['source'] in shown and edge['target'] in shown]
    return {
        'nodes': sorted(out_nodes, key=lambda n: (n['hops'], n['label'])),
        'edges': out_edges,
        'roots': [key(*root) for root in roots],
        'truncated': truncated,
    }


def neighbours(obj):
    """
    Rows touching one object for its Relationships tab and card:
    {'needs': [...], 'needed_by': [...]} of (edge row, other end (ct, pk)).
    """
    ct = ContentType.objects.get_for_model(obj)
    me = (ct.pk, obj.pk)
    needs, needed_by = [], []
    rows = EdgeIndex.objects.filter(
        Q(source_type=ct, source_id=obj.pk) | Q(target_type=ct, target_id=obj.pk),
    ).values(*EDGE_FIELDS)
    for row in rows:
        src, tgt = (row['source_type_id'], row['source_id']), (row['target_type_id'], row['target_id'])
        if src == me:
            needs.append((row, tgt))
        if tgt == me:
            (needs if row['symmetric'] else needed_by).append((row, src))
    return {'needs': needs, 'needed_by': needed_by}
