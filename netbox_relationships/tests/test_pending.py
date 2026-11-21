"""Relationships waiting for approval in netbox-change-approval."""
from unittest import mock

from django.db.models import F
from django.test import TestCase

from .. import graph
from ..graph import object_key, parse_key
from ..impact import analyse
from ..models import Relationship
from .utils import make_devices, make_superuser, needs


def pending(*rels):
    """Stands in for change-approval's pending create requests of `rels`."""
    ids = Relationship.objects.filter(pk__in=[rel.pk for rel in rels]).annotate(object_id=F('pk'))
    return mock.patch('netbox_relationships.integrations.pending_relationship_ids',
                      return_value=ids.values('object_id'))


class PendingTests(TestCase):
    def setUp(self):
        self.app, self.db, self.disk = make_devices('app', 'db', 'disk')
        self.user = make_superuser()
        self.approved = needs(self.app, self.db)
        self.waiting = needs(self.app, self.disk)

    def test_impact_leaves_out_pending_links(self):
        with pending(self.waiting):
            result = analyse(self.user, [parse_key(object_key(self.disk))])
        self.assertEqual(result['affected'], [])

    def test_graph_marks_pending_links(self):
        with pending(self.waiting):
            data = graph.build(self.user, [parse_key(object_key(self.app))])
        marks = {edge['relationship']: edge['pending'] for edge in data['edges']}
        self.assertEqual(marks, {self.approved.pk: False, self.waiting.pk: True})
