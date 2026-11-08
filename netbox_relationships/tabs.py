"""
The "Relationships" and "Dependency graph" tabs on object pages. Registered
from ready() for every model in the `object_types` setting (or
constants.TAB_MODELS), so they work on core and plugin models alike.
"""
import logging

from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from netbox.views import generic
from utilities.views import ViewTab, get_default_template, register_model_view

from . import settings
from .choices import CriticalityChoices, ImpactChoices, StatusChoices
from .constants import MANUAL, TAB_MODELS
from .graph import neighbours, resolve
from .models import EdgeIndex

logger = logging.getLogger('netbox_relationships.tabs')

PERMISSION = 'netbox_relationships.view_relationship'


def edge_count(obj):
    ct = ContentType.objects.get_for_model(obj)
    return EdgeIndex.objects.filter(
        Q(source_type=ct, source_id=obj.pk) | Q(target_type=ct, target_id=obj.pk),
    ).count()


def choice(choices, value):
    """(label, colour) of a choice value, for badges."""
    labels = {item[0]: item[1] for item in choices.CHOICES}
    return labels.get(value, value), choices.colors.get(value)


def rows_for(user, obj):
    """
    The Relationships tab's tables: {'needs': [...], 'needed_by': [...],
    'derived_needs': [...], 'derived_needed_by': [...]}, each row a dict.
    """
    found = neighbours(obj)
    others = {other for _row, other in found['needs'] + found['needed_by']}
    nodes = resolve(user, others)
    out = {'needs': [], 'needed_by': [], 'derived_needs': [], 'derived_needed_by': []}
    for side, pairs in (('needs', found['needs']), ('needed_by', found['needed_by'])):
        for row, other in pairs:
            entry = {
                'label': row['label'] if side == 'needs' else row['reverse_label'],
                'other': nodes[other],
                'status': choice(StatusChoices, row['status']),
                'criticality': choice(CriticalityChoices, row['criticality']),
                'criticality_value': row['criticality'],
                'impact': choice(ImpactChoices, row['impact']),
                'relationship_id': row['relationship_id'],
                'kind': row['origin'],
                'color': row['color'],
            }
            target = side if row['origin'] == MANUAL else f'derived_{side}'
            out[target].append(entry)
    for rows in out.values():
        rows.sort(key=lambda r: (r['label'], r['other']['label']))
    return out


class RelationshipsTabView(generic.ObjectView):
    template_name = 'netbox_relationships/object_relationships.html'
    tab = ViewTab(label=_('Relationships'), badge=edge_count, permission=PERMISSION, weight=2100)

    def get_extra_context(self, request, instance):
        ct = ContentType.objects.get_for_model(instance)
        return {
            'base_template': get_default_template(type(instance)),
            'rows': rows_for(request.user, instance),
            'object_key': f'{ct.pk}:{instance.pk}',
            'add_url': (
                f"{reverse('plugins:netbox_relationships:relationship_add')}"
                f"?source_content_type={ct.pk}&source_object_id={instance.pk}"
                f"&return_url={request.path}"
            ),
        }


class GraphTabView(generic.ObjectView):
    template_name = 'netbox_relationships/object_graph.html'
    tab = ViewTab(label=_('Dependency graph'), permission=PERMISSION, weight=2110)

    def get_extra_context(self, request, instance):
        ct = ContentType.objects.get_for_model(instance)
        return {
            'base_template': get_default_template(type(instance)),
            'object_key': f'{ct.pk}:{instance.pk}',
            'default_depth': settings.depth(),
            'depth_choices': range(1, int(settings.get('max_depth')) + 1),
            'version': asset_version(),
        }


def asset_version():
    from . import NetBoxRelationshipsConfig
    return NetBoxRelationshipsConfig.version


def tab_models():
    labels = settings.get('object_types') or TAB_MODELS
    found = []
    for label in labels:
        try:
            found.append(apps.get_model(label))
        except (LookupError, ValueError):
            logger.warning('netbox_relationships: unknown object type %r in object_types', label)
    return found


def register():
    for model in tab_models():
        name = model._meta.model_name
        attrs = {'queryset': model.objects.all(), '__module__': __name__}
        register_model_view(model, 'relationships', path='relationships')(
            type(f'{name}RelationshipsTab', (RelationshipsTabView,), dict(attrs)),
        )
        register_model_view(model, 'dependency_graph', path='dependency-graph')(
            type(f'{name}GraphTab', (GraphTabView,), dict(attrs)),
        )
