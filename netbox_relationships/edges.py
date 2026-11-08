"""
Keeps the edge index (models.EdgeIndex) in step with relationships and with
NetBox's own data.

- sync_relationship() / drop_relationship(): one hand-made relationship.
- refresh(): the derived edges of some owners of one provider, after they
  changed (called from signals.py).
- forget_object(): every edge touching an object that is being deleted.
- rebuild(): the whole table, from scratch (nightly job, management command).
"""
import logging

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Q

from . import settings
from .constants import MANUAL
from .derived import PROVIDERS
from .models import EdgeIndex, Relationship

logger = logging.getLogger('netbox_relationships.edges')

BATCH = 2000


def _ct(label):
    app_label, model_name = label.split('.')
    return ContentType.objects.get_by_natural_key(app_label, model_name)


def _manual_row(rel):
    rtype = rel.type
    return EdgeIndex(
        source_type_id=rel.source_type_id, source_id=rel.source_id,
        target_type_id=rel.target_type_id, target_id=rel.target_id,
        origin=MANUAL, relationship=rel, rtype=rtype,
        label=rtype.forward_label, reverse_label=rtype.reverse_label,
        impact=rtype.impact, symmetric=rtype.symmetric,
        status=rel.status, criticality=rel.criticality, color=rtype.color,
    )


def sync_relationship(rel):
    """Write (or rewrite) the index row of one relationship."""
    with transaction.atomic():
        EdgeIndex.objects.filter(relationship_id=rel.pk).delete()
        _manual_row(rel).save()


def drop_relationship(pk):
    EdgeIndex.objects.filter(relationship_id=pk).delete()


def sync_type(rtype):
    """Labels, impact and colour of a type changed: rewrite its rows in place."""
    EdgeIndex.objects.filter(origin=MANUAL, rtype=rtype).update(
        label=rtype.forward_label, reverse_label=rtype.reverse_label,
        impact=rtype.impact, symmetric=rtype.symmetric, color=rtype.color,
    )


def _derived_rows(provider, ids=None):
    owner_ct = _ct(provider.owner)
    rows = []
    for edge in provider.build(ids):
        spec = edge.spec
        if not settings.derived_enabled(spec.key):
            continue
        rows.append(EdgeIndex(
            source_type=_ct(edge.source_model), source_id=edge.source_id,
            target_type=_ct(edge.target_model), target_id=edge.target_id,
            origin=spec.key, owner_type=owner_ct, owner_id=edge.owner_id,
            label=spec.label, reverse_label=spec.reverse_label,
            impact=spec.impact, symmetric=spec.symmetric, color=spec.color,
        ))
    return rows


def refresh(provider, ids):
    """Rewrite the derived rows of these owners of `provider`."""
    ids = [pk for pk in ids if pk]
    if not ids or not any(settings.derived_enabled(key) for key in provider.keys):
        return
    with transaction.atomic():
        EdgeIndex.objects.filter(
            origin__in=provider.keys, owner_type=_ct(provider.owner), owner_id__in=ids,
        ).delete()
        EdgeIndex.objects.bulk_create(_derived_rows(provider, ids), batch_size=BATCH)


def forget_object(instance):
    """
    Drop every edge that starts or ends at `instance`, or that it owns. Its
    hand-made relationships are deleted separately (signals.py) so the
    change log records them.
    """
    ct = ContentType.objects.get_for_model(instance)
    EdgeIndex.objects.filter(
        Q(source_type=ct, source_id=instance.pk) | Q(target_type=ct, target_id=instance.pk)
        | Q(owner_type=ct, owner_id=instance.pk),
    ).delete()


def rebuild():
    """Rebuild the whole index. Returns {origin: row count}."""
    counts = {}
    with transaction.atomic():
        EdgeIndex.objects.all().delete()
        manual = [_manual_row(rel) for rel in Relationship.objects.select_related('type')]
        EdgeIndex.objects.bulk_create(manual, batch_size=BATCH)
        counts[MANUAL] = len(manual)
        for provider in PROVIDERS:
            rows = _derived_rows(provider)
            EdgeIndex.objects.bulk_create(rows, batch_size=BATCH)
            for row in rows:
                counts[row.origin] = counts.get(row.origin, 0) + 1
    logger.info('Rebuilt the relationship index: %s', counts)
    return counts
