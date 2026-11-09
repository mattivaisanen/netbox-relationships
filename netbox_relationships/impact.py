"""
Impact analysis: what stops working when some objects fail (or go into
maintenance, which is computed the same way). Read only.

Starting from the failed objects, walk "up" (to what needs them) along
edges whose impact is hard or soft:

- over a hard edge, a failed or down target takes the source down, a
  degraded one leaves it degraded, an at-risk one leaves it at risk;
- over a soft edge, anything worse than at risk leaves the source degraded;
- hard edges in a redundancy group (the uplinks of a switch, the hosts of a
  cluster) count together: the source goes down only when fewer than
  `group_min` of the group's targets still work. Until then, losing one
  leaves it *at risk*: it works, but without its spare.

States only get worse (at risk -> degraded -> down), so the walk ends.
Every affected object remembers the edge that set its state, which gives
the "why" chain shown with each result.
"""
from collections import Counter, defaultdict

from django.contrib.contenttypes.models import ContentType

from . import settings
from .choices import ImpactChoices, ImpactStateChoices, ServiceKindChoices, StatusChoices
from .graph import EDGE_FIELDS, UP, Filters, _frontier_q, edges_from, key, resolve
from .models import EdgeIndex

FAILED, DOWN = ImpactStateChoices.FAILED, ImpactStateChoices.DOWN
DEGRADED, AT_RISK = ImpactStateChoices.DEGRADED, ImpactStateChoices.AT_RISK
_RANK = {None: 0, AT_RISK: 1, DEGRADED: 2, DOWN: 3, FAILED: 4}
_LOST = (FAILED, DOWN)

#: The most rounds the walk runs; far more than any real chain.
MAX_ROUNDS = 100


def _over(impact, target_state):
    """The state an ungrouped edge passes on to its source."""
    if impact == ImpactChoices.HARD:
        return {FAILED: DOWN, DOWN: DOWN, DEGRADED: DEGRADED, AT_RISK: AT_RISK}.get(target_state)
    if impact == ImpactChoices.SOFT and target_state in (FAILED, DOWN, DEGRADED):
        return DEGRADED
    return None


def _far_end(row, source):
    """The (ct, pk) of an edge row's end that isn't `source`."""
    src = (row['source_type_id'], row['source_id'])
    return (row['target_type_id'], row['target_id']) if src == source else src


def _groups(keys, filters):
    """{(source, group): [edge rows]} for the hard grouped edges of these (source, group) pairs."""
    sources = {source for source, _group in keys}
    names = {group for _source, group in keys}
    rows = filters.apply(EdgeIndex.objects.filter(group__in=names, impact=ImpactChoices.HARD))
    found = defaultdict(list)
    for row in rows.filter(_frontier_q(sources, 'source')).values(*EDGE_FIELDS):
        pair = ((row['source_type_id'], row['source_id']), row['group'])
        if pair in keys:
            found[pair].append(row)
    return found


def _group_state(rows, state):
    """(new state, the edge row that explains it) for one redundancy group."""
    lost = [row for row in rows if state.get((row['target_type_id'], row['target_id'])) in _LOST]
    weak = [row for row in rows if state.get((row['target_type_id'], row['target_id'])) in (DEGRADED, AT_RISK)]
    needed = max(1, min(row['group_min'] for row in rows))
    if len(rows) - len(lost) < needed:
        return DOWN, lost[0]
    if lost:
        return AT_RISK, lost[0]
    if weak:
        return AT_RISK, weak[0]
    return None, None


def analyse(user, failed, include_planned=None):
    """
    failed: iterable of (ct, pk). Returns a dict:
    {'failed': [...], 'affected': [...], 'summary': {...}, 'truncated': bool,
    'links': {failed node: (all links, links that carry impact)}}.
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

    def worsen(source, new, row, target):
        """Set a worse state on `source`; True when it changed."""
        nonlocal truncated
        if new is None or _RANK[new] <= _RANK[state.get(source)]:
            return False
        if source not in state and len(state) >= max_nodes:
            truncated = True
            return False
        state[source] = new
        via[source] = (row, target)
        hops[source] = hops[target] + 1
        return True

    for _round in range(MAX_ROUNDS):
        if not frontier:
            break
        changed = set()
        grouped = set()
        for row in edges_from(frontier, UP, filters):
            source = row['next']
            target = _far_end(row, source)
            if target not in state:
                continue
            if row['group'] and row['impact'] == ImpactChoices.HARD:
                grouped.add((source, row['group']))
            elif worsen(source, _over(row['impact'], state[target]), row, target):
                changed.add(source)
        for (source, _group), rows in _groups(grouped, filters).items():
            new, row = _group_state(rows, state)
            if row is not None and worsen(source, new, row, (row['target_type_id'], row['target_id'])):
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
        'links': _link_counts(failed) if not affected else {},
    }


def _link_counts(nodes):
    """
    {node key: (links, links that carry impact upward)} for objects whose
    failure affected nothing, so the page can say why.
    """
    counts = {}
    for node in nodes:
        ct_id, pk = node
        touching = EdgeIndex.objects.filter(_frontier_q({node}, 'source') | _frontier_q({node}, 'target'))
        impacting = EdgeIndex.objects.filter(
            _frontier_q({node}, 'target'), symmetric=False,
        ).exclude(impact=ImpactChoices.NONE)
        counts[key(ct_id, pk)] = (touching.count(), impacting.count())
    return counts


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
        'at_risk': counts.get(AT_RISK, 0),
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
            'at_risk': result['summary']['at_risk'],
            'business_services': [clean(n) for n in result['summary']['business_services']],
            'owners': result['summary']['owners'],
            'tenants': result['summary']['tenants'],
        },
        'truncated': result['truncated'],
        'links': {
            node: {'links': total, 'impacting': impacting} for node, (total, impacting) in result['links'].items()
        },
    }


def object_ids(objects):
    """(ct, pk) pairs for model instances."""
    return {(ContentType.objects.get_for_model(obj).pk, obj.pk) for obj in objects}


__all__ = ('analyse', 'serializable', 'object_ids', 'key')
