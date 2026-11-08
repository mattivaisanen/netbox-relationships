from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from extras.models import Bookmark

from ..models import Relationship
from .utils import make_devices, make_superuser, needs


class PrepareUninstallTests(TestCase):
    def test_removes_rows_that_point_at_plugin_objects(self):
        app, db = make_devices('app', 'db')
        rel = needs(app, db)
        Bookmark.objects.create(user=make_superuser(), object=rel)

        call_command('prepare_relationships_uninstall', interactive=False, stdout=StringIO())
        self.assertFalse(Bookmark.objects.exists())
        self.assertTrue(Relationship.objects.filter(pk=rel.pk).exists())
