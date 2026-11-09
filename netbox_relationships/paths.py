"""
"Path to the top" for one object: the chains of things it needs, down to
objects that need nothing more (a core switch, a circuit, a power panel),
and which single objects it can't lose. Read only.

The object's dependency subgraph is loaded once (one query per hop). Then
each object in it is failed in turn, in memory, with the same rules as
impact analysis (redundancy groups included):

- a single point of failure takes the object down on its own;
- a "spare-less" object leaves it at risk: it keeps working, without its
  spare.
"""
from collections import defaultdict

from . import settings
from .choices import ImpactChoices, ImpactStateChoices, StatusChoices
from .graph import DOWN, Filters, resolve, walk
from .impact import _RANK, _group_state, _over

FAILED, AT_RISK = ImpactStateChoices.FAILED, ImpactStateChoices.AT_RISK

#: Most chains listed; the rest are counted.
MAX_PATHS = 25


def _end(row, side):
    return row[f'{side}_type_id'], row[f'{side}_id']


def simulate(rows, failed):
    """
    States of every node after `failed` fails, over the edge rows given
    (all directed, all carrying impact). Pure: no queries.
    """
    by_target = defaultdict(list)
    groups = defaultdict(list)
    for row in rows:
        by_target[_end(row, 'target')].append(row)
        if row['group'] and row['impact'] == ImpactChoices.HARD:
            groups[(_end(row, 'source'), row['group'])].append(row)
    state = {failed: FAILED}
    frontier = {failed}
    while frontier:
        changed = set()
        for target in frontier:
            for row in by_target[target]:
                source = _end(row, 'source')
                if row['group'] and row['impact'] == ImpactChoices.HARD:
                    new, _why = _group_state(groups[(source, row['group'])], state)
                else:
                    new = _over(row['impact'], state[target])
                if new is not None and _RANK[new] > _RANK[state.get(source)]:
                    state[source] = new
                    changed.add(source)
        frontier = changed
    return state


def _chains(start, rows):
    """Every chain from `start` to a node with no further needs (at most MAX_PATHS)."""
    out = defaultdict(list)
    for row in rows:
        out[_end(row, 'source')].append(_end(row, 'target'))
    chains, more = [], 0
    stack = [(start, [start])]
    while stack:
        node, chain = stack.pop()
        nexts = [n for n in out[node] if n not in chain]
        if not nexts:
            if len(chain) > 1:
                if len(chains) < MAX_PATHS:
                    chains.append(chain)
                else:
                    more += 1
            continue
        for nxt in sorted(nexts, reverse=True):
            stack.append((nxt, chain + [nxt]))
    chains.sort(key=len)
    return chains, more


def analyse(user, node):
    """
    For one (ct, pk): {'chains': [[node dict, ...], ...], 'more': int,
    'single_points': [node dict], 'spares': [node dict], 'truncated': bool}.
    Empty chains when the object needs nothing.
    """
    filters = Filters(statuses=[StatusChoices.ACTIVE, StatusChoices.DECOMMISSIONING], impacting_only=True)
    hops, edges, truncated = walk({node}, DOWN, int(settings.get('max_depth')), filters,
                                  int(settings.get('max_nodes')))
    rows = [row for row in edges.values() if not row['symmetric']]
    if not rows:
        return {'chains': [], 'more': 0, 'single_points': [], 'spares': [], 'truncated': truncated}

    single, spares = [], []
    for candidate in hops:
        if candidate == node:
            continue
        state = simulate(rows, candidate).get(node)
        if state == ImpactStateChoices.DOWN:
            single.append(candidate)
        elif state == AT_RISK:
            spares.append(candidate)

    chains, more = _chains(node, rows)
    nodes = resolve(user, hops)

    def clean(n):
        return {k: v for k, v in nodes[n].items() if k != 'object'}

    def by_distance(items):
        return [clean(n) for n in sorted(items, key=lambda n: (hops[n], nodes[n]['label']))]

    return {
        'chains': [[clean(n) for n in chain[1:]] for chain in chains],
        'more': more,
        'single_points': by_distance(single),
        'spares': by_distance(spares),
        'truncated': truncated,
    }
