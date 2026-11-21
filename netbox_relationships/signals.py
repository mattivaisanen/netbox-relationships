"""
Keeps the edge index current. Connected from NetBoxRelationshipsConfig.ready().

- A relationship saved or deleted rewrites its own index row.
- A relationship type saved rewrites the labels of its rows.
- Saving or deleting a NetBox object an edge provider watches (a VM, a
  cable termination, ...) refreshes that provider's rows for the owners
  it affects.
- Deleting an object first deletes its relationships and every index row
  that touches it. The relationships are deleted as part of the outer
  delete (same `origin`), so the change log records them and
  netbox-change-approval treats them as part of that one delete.
- Saving or deleting a network tier, or changing its roles, rewrites every
  network cable link once the change is committed.
- After `manage.py migrate` the whole index is rebuilt, but only when this
  plugin's migrations ran or the index is empty: netbox-docker runs migrate
  on every start, and a restart shouldn't pay for a full rebuild.
"""
import logging

from django.apps import apps
from django.db import models, router, transaction
from django.db.models.deletion import Collector
from django.db.models.signals import m2m_changed, post_delete, post_migrate, post_save, pre_delete

from . import edges
from .derived import PROVIDERS
from .models import EdgeIndex, LogicalService, NetworkTier, Relationship, RelationshipType

logger = logging.getLogger('netbox_relationships.signals')

#: Apps whose objects never have relationships; their deletes are skipped
#: without a query (change log, sessions, caches, ...).
_SKIP_APPS = {'admin', 'auth', 'contenttypes', 'sessions', 'core', 'extras', 'users', 'django_rq', 'taggit'}

#: Keeps receivers alive: Django holds signal receivers weakly.
_receivers = []

APP_LABEL = 'netbox_relationships'


def _uid(what):
    """A dispatch_uid in the shared '<app_label>:<what>' form."""
    return f'{APP_LABEL}:{what}'


def _relationship_saved(sender, instance, **kwargs):
    edges.sync_relationship(instance)


def _relationship_deleted(sender, instance, **kwargs):
    edges.drop_relationship(instance.pk)


def _type_saved(sender, instance, created, **kwargs):
    if not created:
        edges.sync_type(instance)


def _tiers_changed(sender, **kwargs):
    """Tiers or their roles changed: redo the network links once, after commit."""
    if kwargs.get('action', 'post_').startswith('pre_'):
        return
    connection = transaction.get_connection()
    if getattr(connection, '_nbr_network_pending', False):
        return
    connection._nbr_network_pending = True

    def run():
        connection._nbr_network_pending = False
        try:
            edges.refresh_network()
        except Exception:
            logger.exception('Could not refresh network links after a tier change')

    transaction.on_commit(run)


def _object_deleting(sender, instance, origin=None, **kwargs):
    """Before an object is deleted: drop its relationships and edges."""
    if instance.pk is None:
        return
    from django.contrib.contenttypes.models import ContentType
    from django.db.models import Q

    ct = ContentType.objects.get_for_model(instance)
    touching = Q(source_type=ct, source_id=instance.pk) | Q(target_type=ct, target_id=instance.pk)
    if not EdgeIndex.objects.filter(touching | Q(owner_type=ct, owner_id=instance.pk)).exists():
        return
    relationships = list(Relationship.objects.filter(touching))
    if relationships:
        # Delete them as Model.delete() would (signals, change log), but
        # with the outer delete's origin: netbox-change-approval then sees
        # them as part of deleting `origin`, which was already let through,
        # instead of as separate deletes that each need approval.
        if not isinstance(origin, models.Model):
            origin = instance
        collector = Collector(using=router.db_for_write(Relationship), origin=origin)
        collector.collect(relationships)
        collector.delete()
    edges.forget_object(instance)


def _watched_models():
    """
    Models whose deletes are checked for relationships: every installed
    model except those that never have any (Django internals, NetBox's
    change log and users, this plugin's own tables but LogicalService).
    Reads the app registry only, no database.
    """
    for model in apps.get_models():
        meta = model._meta
        if meta.app_label in _SKIP_APPS or meta.auto_created or meta.proxy:
            continue
        if meta.app_label == APP_LABEL and model is not LogicalService:
            continue
        yield model


def _refresher(provider, owners_of):
    def receiver(sender, instance, **kwargs):
        try:
            edges.refresh(provider, owners_of(instance))
        except Exception:
            # Never break a NetBox save over the index; the nightly rebuild fixes it.
            logger.exception('Could not refresh %s edges for %r', type(provider).__name__, instance)
    return receiver


def connect():
    post_save.connect(_relationship_saved, sender=Relationship, dispatch_uid=_uid('relationship_saved'))
    post_delete.connect(_relationship_deleted, sender=Relationship, dispatch_uid=_uid('relationship_deleted'))
    post_save.connect(_type_saved, sender=RelationshipType, dispatch_uid=_uid('type_saved'))
    post_save.connect(_tiers_changed, sender=NetworkTier, dispatch_uid=_uid('tier_saved'))
    post_delete.connect(_tiers_changed, sender=NetworkTier, dispatch_uid=_uid('tier_deleted'))
    m2m_changed.connect(_tiers_changed, sender=NetworkTier.roles.through, dispatch_uid=_uid('tier_roles'))

    # One connection per model, so deletes of Django internals, change log
    # entries and the like never reach the receiver.
    for model in _watched_models():
        pre_delete.connect(_object_deleting, sender=model, dispatch_uid=_uid(f'deleting_{model._meta.label_lower}'))

    for provider in PROVIDERS:
        for label, owners_of in provider.watched():
            model = apps.get_model(label)
            receiver = _refresher(provider, owners_of)
            _receivers.append(receiver)
            uid = f'{type(provider).__name__}_{label}'
            post_save.connect(receiver, sender=model, dispatch_uid=_uid(f'{uid}_save'))
            post_delete.connect(receiver, sender=model, dispatch_uid=_uid(f'{uid}_delete'))


def _needs_rebuild(plan):
    """True when this migrate applied one of our migrations, or the index is empty."""
    if any(migration.app_label == APP_LABEL for migration, _backwards in plan or ()):
        return True
    return not EdgeIndex.objects.exists()


def _migrated(sender, using='default', plan=None, **kwargs):
    """Rebuild the index after this plugin's migrations ran, or when it is empty."""
    try:
        if not _needs_rebuild(plan):
            return
        counts = edges.rebuild()
        logger.info('netbox_relationships: rebuilt the relationship index after migrate: %s', counts)
    except Exception:
        # Never fail a migrate over the index; the nightly job and the command can rebuild it.
        logger.exception('netbox_relationships: could not rebuild the relationship index after migrate')


def connect_post_migrate(app_config):
    post_migrate.connect(_migrated, sender=app_config, dispatch_uid=_uid('post_migrate'))
