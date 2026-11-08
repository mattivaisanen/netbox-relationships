"""
Keeps the edge index current. Connected from NetBoxRelationshipsConfig.ready().

- A relationship saved or deleted rewrites its own index row.
- A relationship type saved rewrites the labels of its rows.
- Saving or deleting a NetBox object an edge provider watches (a VM, a
  cable termination, ...) refreshes that provider's rows for the owners
  it affects.
- Deleting any object first deletes its relationships (one by one, so the
  change log records them) and every index row that touches it.
"""
import logging

from django.apps import apps
from django.db.models.signals import post_delete, post_save, pre_delete

from . import edges
from .derived import PROVIDERS
from .models import EdgeIndex, LogicalService, Relationship, RelationshipType

logger = logging.getLogger('netbox_relationships.signals')

#: Apps whose objects never have relationships; their deletes are skipped
#: without a query (change log, sessions, caches, ...).
_SKIP_APPS = {'admin', 'auth', 'contenttypes', 'sessions', 'core', 'extras', 'users', 'django_rq', 'taggit'}

#: Keeps receivers alive: Django holds signal receivers weakly.
_receivers = []


def _relationship_saved(sender, instance, **kwargs):
    edges.sync_relationship(instance)


def _relationship_deleted(sender, instance, **kwargs):
    edges.drop_relationship(instance.pk)


def _type_saved(sender, instance, created, **kwargs):
    if not created:
        edges.sync_type(instance)


def _object_deleting(sender, instance, **kwargs):
    """Before any object is deleted: drop its relationships and edges."""
    meta = getattr(sender, '_meta', None)
    if meta is None or meta.app_label in _SKIP_APPS or sender in (EdgeIndex, Relationship, RelationshipType):
        return
    if meta.app_label == 'netbox_relationships' and sender is not LogicalService:
        return
    if instance.pk is None:
        return
    from django.contrib.contenttypes.models import ContentType
    from django.db.models import Q

    ct = ContentType.objects.get_for_model(instance)
    touching = Q(source_type=ct, source_id=instance.pk) | Q(target_type=ct, target_id=instance.pk)
    if not EdgeIndex.objects.filter(touching | Q(owner_type=ct, owner_id=instance.pk)).exists():
        return
    for rel in Relationship.objects.filter(touching):
        rel.delete()
    edges.forget_object(instance)


def _refresher(provider, owners_of):
    def receiver(sender, instance, **kwargs):
        try:
            edges.refresh(provider, owners_of(instance))
        except Exception:
            # Never break a NetBox save over the index; the nightly rebuild fixes it.
            logger.exception('Could not refresh %s edges for %r', type(provider).__name__, instance)
    return receiver


def connect():
    post_save.connect(_relationship_saved, sender=Relationship, dispatch_uid='nbr_relationship_saved')
    post_delete.connect(_relationship_deleted, sender=Relationship, dispatch_uid='nbr_relationship_deleted')
    post_save.connect(_type_saved, sender=RelationshipType, dispatch_uid='nbr_type_saved')
    pre_delete.connect(_object_deleting, dispatch_uid='nbr_object_deleting')

    for provider in PROVIDERS:
        for label, owners_of in provider.watched():
            model = apps.get_model(label)
            receiver = _refresher(provider, owners_of)
            _receivers.append(receiver)
            uid = f'nbr_{type(provider).__name__}_{label}'
            post_save.connect(receiver, sender=model, dispatch_uid=f'{uid}_save')
            post_delete.connect(receiver, sender=model, dispatch_uid=f'{uid}_delete')
