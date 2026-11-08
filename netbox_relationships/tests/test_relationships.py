"""Relationships, the edge index and impact analysis."""
from django.core.exceptions import ValidationError
from django.test import TestCase

from ..graph import object_key, parse_key
from ..impact import analyse
from ..models import EdgeIndex, Relationship
from .utils import make_devices, make_superuser, needs


def node(obj):
    return parse_key(object_key(obj))


class RelationshipTests(TestCase):
    def setUp(self):
        self.app, self.db, self.disk = make_devices('app', 'db', 'disk')

    def test_saving_and_deleting_updates_the_index(self):
        rel = needs(self.app, self.db)
        self.assertTrue(EdgeIndex.objects.filter(relationship=rel).exists())
        rel.delete()
        self.assertFalse(EdgeIndex.objects.filter(relationship_id=rel.pk).exists())

    def test_self_link_is_refused(self):
        with self.assertRaises(ValidationError):
            needs(self.app, self.app)

    def test_loop_is_refused(self):
        needs(self.app, self.db)
        needs(self.db, self.disk)
        with self.assertRaises(ValidationError):
            needs(self.disk, self.app)

    def test_deleting_an_object_removes_its_relationships(self):
        needs(self.app, self.db)
        self.db.delete()
        self.assertFalse(Relationship.objects.exists())
        self.assertFalse(EdgeIndex.objects.filter(origin='manual').exists())


class ImpactTests(TestCase):
    def setUp(self):
        self.app, self.db, self.disk = make_devices('app', 'db', 'disk')
        self.user = make_superuser()

    def states(self, *failed):
        result = analyse(self.user, [node(obj) for obj in failed])
        return {entry['label']: entry['state'] for entry in result['affected']}

    def test_hard_dependency_goes_down_along_the_chain(self):
        needs(self.app, self.db)
        needs(self.db, self.disk)
        self.assertEqual(self.states(self.disk), {'db': 'down', 'app': 'down'})

    def test_nothing_above_is_untouched(self):
        needs(self.app, self.db)
        self.assertEqual(self.states(self.app), {})
