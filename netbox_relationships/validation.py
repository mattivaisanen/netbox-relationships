"""
Checks a relationship must pass before it is saved. Used by
Relationship.clean(), so forms, bulk import and the REST API all run them.
"""
from django.utils.translation import gettext as _

from .choices import CardinalityChoices
from .constants import MANUAL

#: How far the loop check follows a chain before giving up.
CYCLE_SEARCH_LIMIT = 5000


def relationship_errors(rel):
    """{field: message} for everything wrong with `rel`, or {}."""
    from .models import Relationship

    errors = {}
    if not rel.type_id or not rel.source_type_id or not rel.target_type_id:
        return errors
    rtype = rel.type

    source, target = rel.source, rel.target
    if source is None:
        errors['source_id'] = _('No such object.')
    if target is None:
        errors['target_id'] = _('No such object.')
    if errors:
        return errors

    if rel.source_type_id == rel.target_type_id and rel.source_id == rel.target_id:
        errors['target_id'] = _('An object cannot have a relationship with itself.')
        return errors

    allowed = set(rtype.source_types.values_list('pk', flat=True))
    if allowed and rel.source_type_id not in allowed:
        errors['source_type'] = _('"{type}" does not allow this kind of source.').format(type=rtype)
    allowed = set(rtype.target_types.values_list('pk', flat=True))
    if allowed and rel.target_type_id not in allowed:
        errors['target_type'] = _('"{type}" does not allow this kind of target.').format(type=rtype)

    if rtype.require_description and not rel.description:
        errors['description'] = _('"{type}" requires a reason.').format(type=rtype)

    others = Relationship.objects.filter(type=rtype).exclude(pk=rel.pk)

    # A symmetric link from B to A is the same link as A to B.
    if rtype.symmetric and others.filter(
        source_type=rel.target_type_id, source_id=rel.target_id,
        target_type=rel.source_type_id, target_id=rel.source_id,
    ).exists():
        errors['target_id'] = _('This relationship already exists the other way round.')

    one_target = rtype.cardinality in (CardinalityChoices.MANY_TO_ONE, CardinalityChoices.ONE_TO_ONE)
    one_source = rtype.cardinality in (CardinalityChoices.ONE_TO_MANY, CardinalityChoices.ONE_TO_ONE)
    if one_target and others.filter(source_type=rel.source_type_id, source_id=rel.source_id).exists():
        errors['source_id'] = _('This object already has a "{type}" relationship.').format(type=rtype)
    if one_source and others.filter(target_type=rel.target_type_id, target_id=rel.target_id).exists():
        errors['target_id'] = _('This object is already the target of a "{type}" relationship.').format(type=rtype)

    if not rtype.allow_cycles and not rtype.symmetric and 'target_id' not in errors:
        chain = find_chain(rtype, (rel.target_type_id, rel.target_id), (rel.source_type_id, rel.source_id), rel.pk)
        if chain:
            names = ' → '.join(str(obj) for obj in [source] + chain)
            errors['target_id'] = _(
                'This would create a loop, which "{type}" does not allow: {chain}'
            ).format(type=rtype, chain=names)

    return errors


def find_chain(rtype, start, goal, exclude_pk=None):
    """
    Objects on a chain of `rtype` links from `start` to `goal`, both
    included, or [] when there is none. `start` and `goal` are
    (content type id, object id). Breadth-first, so the chain is a shortest one.
    """
    from django.contrib.contenttypes.models import ContentType

    from .models import EdgeIndex

    rows = EdgeIndex.objects.filter(origin=MANUAL, rtype=rtype)
    if exclude_pk:
        rows = rows.exclude(relationship_id=exclude_pk)
    # Small enough to read at once: one type's hand-made links.
    nexts = {}
    for row in rows.values_list('source_type_id', 'source_id', 'target_type_id', 'target_id')[:CYCLE_SEARCH_LIMIT]:
        nexts.setdefault((row[0], row[1]), []).append((row[2], row[3]))

    came_from = {start: None}
    queue = [start]
    while queue:
        node = queue.pop(0)
        if node == goal:
            path = []
            while node is not None:
                path.append(node)
                node = came_from[node]
            path.reverse()
            return [_load(ContentType, ct, pk) for ct, pk in path]
        for nxt in nexts.get(node, ()):
            if nxt not in came_from:
                came_from[nxt] = node
                queue.append(nxt)
    return []


def _load(ContentType, ct_id, pk):
    model = ContentType.objects.get_for_id(ct_id).model_class()
    obj = model.objects.filter(pk=pk).first() if model else None
    return obj if obj is not None else f'#{pk}'
