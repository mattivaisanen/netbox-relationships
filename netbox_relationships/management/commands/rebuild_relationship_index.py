"""Rebuild the edge index from relationships and NetBox's own data."""
from django.core.management.base import BaseCommand

from netbox_relationships.edges import rebuild


class Command(BaseCommand):
    help = (
        'Rebuild the index of all relationships and of the links worked out from NetBox data. '
        'Run after changing the "derived" setting, or if graphs look out of date.'
    )

    def handle(self, *args, **options):
        counts = rebuild()
        for origin, count in sorted(counts.items()):
            self.stdout.write(f'{origin}: {count}')
        self.stdout.write(self.style.SUCCESS(f'Done: {sum(counts.values())} edges.'))
