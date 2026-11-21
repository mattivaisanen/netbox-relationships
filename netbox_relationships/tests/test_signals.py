"""Index upkeep: deletes, rebuild after migrate, the Rebuild button."""
from types import SimpleNamespace
from unittest import mock

from django.db.models.signals import pre_delete
from django.test import TestCase
from django.urls import reverse

from ..models import EdgeIndex, Relationship
from ..signals import _needs_rebuild
from .utils import make_devices, make_superuser, needs


class DeleteTests(TestCase):
    def test_relationships_are_deleted_as_part_of_the_outer_delete(self):
        """netbox-change-approval relies on `origin` naming the object the user deleted."""
        app, db = make_devices('app', 'db')
        needs(app, db)
        origins = []

        def record(sender, instance, origin=None, **kwargs):
            origins.append(origin)

        pre_delete.connect(record, sender=Relationship, dispatch_uid='test:record_origin')
        try:
            db.delete()
        finally:
            pre_delete.disconnect(sender=Relationship, dispatch_uid='test:record_origin')
        self.assertEqual(origins, [db])
        self.assertFalse(Relationship.objects.exists())


class MigrateRebuildTests(TestCase):
    def test_rebuilds_only_when_needed(self):
        ours = SimpleNamespace(app_label='netbox_relationships')
        other = SimpleNamespace(app_label='dcim')
        # Empty index: always rebuild.
        self.assertTrue(_needs_rebuild([]))
        app, db = make_devices('app', 'db')
        needs(app, db)
        # Filled index, nothing of ours migrated (a plain restart): no rebuild.
        self.assertFalse(_needs_rebuild([]))
        self.assertFalse(_needs_rebuild([(other, False)]))
        # One of our migrations ran: rebuild.
        self.assertTrue(_needs_rebuild([(ours, False)]))


class RebuildButtonTests(TestCase):
    def test_queues_the_job_instead_of_rebuilding_in_the_request(self):
        self.client.force_login(make_superuser())
        app, db = make_devices('app', 'db')
        needs(app, db)
        EdgeIndex.objects.all().delete()
        with mock.patch('netbox_relationships.jobs.RebuildRelationshipIndexJob.enqueue') as enqueue:
            response = self.client.post(reverse('plugins:netbox_relationships:rebuild_index'))
        self.assertEqual(response.status_code, 302)
        enqueue.assert_called_once()
        # Nothing was rebuilt inline.
        self.assertFalse(EdgeIndex.objects.exists())
