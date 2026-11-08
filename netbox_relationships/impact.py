"""
Impact analysis: what stops working when some objects fail (or go into
maintenance, which is computed the same way). Read only.

Starting from the failed objects, walk "up" (to what needs them) along
edges whose impact is hard or soft:

- over a hard edge, a failed or down target takes the source down;
- anything else that is reached (a soft edge, or a hard edge to a
  degraded target) leaves the source degraded.

States only get worse (degraded -> down), so each object is visited at
most twice and the walk ends. Every affected object remembers the edge
that set its state, which gives the "why" chain shown with each result.
"""
from collections import Counter

from django.contrib.contenttypes.models import ContentType

from . import settings
from .choices import ImpactChoices, ImpactStateChoices, ServiceKindChoices, StatusChoices
from .graph import UP, Filters, edges_from, key, resolve

FAILED, DOWN, DEGRADED = ImpactStateChoices.FAILED, ImpactStateChoices.DOWN, ImpactStateChoices.DEGRADED
_RANK = {None: 0, DEGRADED: 1, DOWN: 2, FAILED: 3}

#: The most rounds the walk runs; far more than any real chain.
MAX_ROUNDS = 100


def analyse(user, failed, include_planned=None):
    """
    failed: iterable of (ct, pk). Returns a dict:
    {'failed': [...], 'affected': [...], 'summary': {...}, 'truncated': bool}.
    Each affected entry has the node fields of graph.resolve() plus 'state',
    'hops' and 'chain' (the objects from it down to a failed one).
    """
    if include_planned is None:
        include_planned = bool(settings.get('include_planned_in_impact'))
    statuses = [StatusChoices.ACTIVE, StatusChoices.DECOMMISSIONING]
    if include_planned:
        statuses.append(StatusChoices.PLANNED)
    filters = Filters(statuses=statuses, impacting_only=True)
    max_nodes = int(settings.get('max_nodes'))

    failed = set(failed)
    state = {node: FAILED for node in failed}
    via = {}  # node -> (edge row, the node it depends on)
    hops = {node: 0 for node in failed}
    frontier = set(failed)
    truncated = False
    for _ in range(MAX_ROUNDS):
        if not frontier:
            break
        changed = set()
        for row in edges_from(frontier, UP, filters):
            source = row['next']
            target = (row['source_type_id'], row['source_id']) if source == (
                row['target_type_id'], row['target_id']) else (row['target_type_id'], row['target_id'])
            if target not in state:
                continue
            hard = row['impact'] == ImpactChoices.HARD and state[target] in (FAILED, DOWN)
            new = DOWN if hard else DEGRADED
            if _RANK[new] <= _RANK[state.get(source)]:
                continue
            if source not in state and len(state) >= max_nodes:
                truncated = True
                continue
            state[source] = new
            via[source] = (row, target)
            hops[source] = hops[target] + 1
            changed.add(source)
        frontier = changed

    nodes = resolve(user, state)
    affected = []
    for node_id, node_state in state.items():
        if node_state == FAILED:
            continue
        entry = {k: v for k, v in nodes[node_id].items()}
        entry.update(state=node_state, hops=hops[node_id], chain=_chain(node_id, via, nodes))
        affected.append(entry)
    affected.sort(key=lambda e: (-_RANK[e['state']], _group_order(e), e['hops'], e['label']))
    failed_nodes = [nodes[node] for node in failed]
    return {
        'failed': failed_nodes,
        'affected': affected,
        'summary': _summary(affected),
        'truncated': truncated,
    }


def _chain(node_id, via, nodes):
    """[{'label', 'url', 'hidden', 'edge'}] from node_id down to the failed object."""
    chain = []
    seen = set()
    current = node_id
    while current is not None and current not in seen:
        seen.add(current)
        node = nodes[current]
        step = via.get(current)
        chain.append({
            'label': node['label'], 'url': node['url'], 'hidden': node['hidden'],
            'edge': step[0]['label'] if step else None,
        })
        current = step[1] if step else None
    return chain


def _group_order(entry):
    """Business services first, then applications, then everything else."""
    obj = entry.get('object')
    if obj is not None and type(obj)._meta.label_lower == 'netbox_relationships.logicalservice':
        return 0 if obj.kind == ServiceKindChoices.BUSINESS_SERVICE else 1
    return 2


def _summary(affected):
    counts = Counter(entry['state'] for entry in affected)
    business, owners, tenants = [], set(), set()
    for entry in affected:
        obj = entry.get('object')
        if obj is None:
            continue
        if type(obj)._meta.label_lower == 'netbox_relationships.logicalservice' and \
                obj.kind == ServiceKindChoices.BUSINESS_SERVICE:
            business.append(entry)
        owner = getattr(obj, 'owner', None)
        if owner is not None:
            owners.add(str(owner))
        tenant = getattr(obj, 'tenant', None)
        if tenant is not None:
            tenants.add(str(tenant))
    return {
        'down': counts.get(DOWN, 0),
        'degraded': counts.get(DEGRADED, 0),
        'business_services': business,
        'owners': sorted(owners),
        'tenants': sorted(tenants),
    }


def serializable(result):
    """The result of analyse() without model instances, for the API."""
    def clean(node):
        return {k: v for k, v in node.items() if k != 'object'}
    return {
        'failed': [clean(n) for n in result['failed']],
        'affected': [clean(n) for n in result['affected']],
        'summary': {
            'down': result['summary']['down'],
            'degraded': result['summary']['degraded'],
            'business_services': [clean(n) for n in result['summary']['business_services']],
            'owners': result['summary']['owners'],
            'tenants': result['summary']['tenants'],
        },
        'truncated': result['truncated'],
    }


def object_ids(objects):
    """(ct, pk) pairs for model instances."""
    return {(ContentType.objects.get_for_model(obj).pk, obj.pk) for obj in objects}


__all__ = ('analyse', 'serializable', 'object_ids', 'key')
