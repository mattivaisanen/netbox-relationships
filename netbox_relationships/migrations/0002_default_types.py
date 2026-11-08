"""Creates the built-in relationship types (constants.DEFAULT_TYPES). All of them can be edited or deleted."""
from django.db import migrations

# A copy, so later changes to constants.py don't change what this migration did.
DEFAULT_TYPES = (
    ('Depends on', 'depends-on', 'depends on', 'is required by', 'dependency', 'hard', False, '2f6fdf'),
    ('Runs on', 'runs-on', 'runs on', 'hosts', 'hosting', 'hard', False, '6b7690'),
    ('Connects to', 'connects-to', 'connects to', 'connects to', 'connectivity', 'none', True, '9aa3b2'),
    ('Sends data to', 'sends-data-to', 'sends data to', 'receives data from', 'data_flow', 'soft', False, '1f7a6b'),
    ('Backed up by', 'backed-up-by', 'is backed up by', 'backs up', 'dependency', 'soft', False, '795548'),
    ('Replicates to', 'replicates-to', 'replicates to', 'is replicated from', 'data_flow', 'soft', False, '00838f'),
    ('Managed by', 'managed-by', 'is managed by', 'manages', 'ownership', 'none', False, '6b4bb8'),
    ('Monitored by', 'monitored-by', 'is monitored by', 'monitors', 'dependency', 'soft', False, '9e9d24'),
    ('Powered by', 'powered-by', 'is powered by', 'powers', 'dependency', 'hard', False, 'e65100'),
    ('Peer of', 'peer-of', 'is a peer of', 'is a peer of', 'informational', 'none', True, '607d8b'),
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
