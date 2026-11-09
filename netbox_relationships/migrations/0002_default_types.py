"""
Creates the built-in relationship types on a new install. All of them can be
edited or deleted. Before 0.2.0 this created eleven types; installs that ran
it then keep them (see constants.COMMON_TYPES for the other seven).
"""
from django.db import migrations

# A copy, so later changes to constants.py don't change what this migration did.
DEFAULT_TYPES = (
    ('Depends on', 'depends-on', 'depends on', 'is required by', 'dependency', 'hard', False, '2f6fdf'),
    ('Runs on', 'runs-on', 'runs on', 'hosts', 'hosting', 'hard', False, '6b7690'),
    ('Connects to', 'connects-to', 'connects to', 'connects to', 'connectivity', 'none', True, '9aa3b2'),
    ('Related to', 'related-to', 'is related to', 'is related to', 'informational', 'none', True, 'b0bec5'),
)


def create(apps, schema_editor):
    RelationshipType = apps.get_model('netbox_relationships', 'RelationshipType')
    for name, slug, forward, reverse, category, impact, symmetric, color in DEFAULT_TYPES:
        RelationshipType.objects.get_or_create(slug=slug, defaults={
            'name': name, 'forward_label': forward, 'reverse_label': reverse, 'category': category,
            'impact': impact, 'symmetric': symmetric, 'allow_cycles': symmetric, 'color': color,
        })


class Migration(migrations.Migration):
    dependencies = [('netbox_relationships', '0001_initial')]
    operations = [migrations.RunPython(create, migrations.RunPython.noop)]
