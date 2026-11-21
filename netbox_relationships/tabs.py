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

from . import paths, settings
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


#: Readable names of edge origins (derived.py spec keys), for the Origin column.
ORIGIN_LABELS = {
    MANUAL: _('Manual'),
    'vm_cluster': _('VM placement'),
    'cluster_hosts': _('Cluster hosts'),
    'service_parent': _('Service'),
    'cables': _('Cables'),
    'power': _('Power'),
    'circuits': _('Circuit'),
    'virtual_chassis': _('Virtual chassis'),
    'logical_parent': _('Service parent'),
    'placement': _('Placement'),
    'ip_prefix': _('IP / prefix'),
}


def link_kind(row, me):
    """'needs', 'needed_by' or 'other' for an edge row seen from `me`."""
    if row['symmetric'] or row['impact'] == ImpactChoices.NONE:
        return 'other'
    return 'needs' if (row['source_type_id'], row['source_id']) == me else 'needed_by'


def rows_for(user, obj):
    """
    The Relationships tab's tables: {'needs': [...], 'needed_by': [...],
    'other': [...]}, each row a dict. "Needs" and "needed by" hold links
    that carry impact; "other" holds connections and informational links.
    Manual and derived links are mixed, with their origin on each row.
    """
    found = neighbours(obj)
    me = (ContentType.objects.get_for_model(obj).pk, obj.pk)
    others = {other for _row, other in found['needs'] + found['needed_by']}
    nodes = resolve(user, others)
    out = {'needs': [], 'needed_by': [], 'other': []}
    seen = set()
    for side, pairs in (('needs', found['needs']), ('needed_by', found['needed_by'])):
        for row, other in pairs:
            if row['pk'] in seen:
                continue
            seen.add(row['pk'])
            outgoing = (row['source_type_id'], row['source_id']) == me
            entry = {
                'label': row['label'] if outgoing or row['symmetric'] else row['reverse_label'],
                'note': row['note'],
                'other': nodes[other],
                'status': choice(StatusChoices, row['status']),
                'criticality': choice(CriticalityChoices, row['criticality']),
                'criticality_value': row['criticality'],
                'impact': choice(ImpactChoices, row['impact']),
                'relationship_id': row['relationship_id'],
                'manual': row['origin'] == MANUAL,
                'origin': ORIGIN_LABELS.get(row['origin'], row['origin']),
                'group': row['group'],
                'group_min': row['group_min'],
                'link_count': row['link_count'],
                'color': row['color'],
            }
            out[link_kind(row, me)].append(entry)
    for rows in out.values():
        rows.sort(key=lambda r: (not r['manual'], r['label'], r['other']['label']))
    return out


class RelationshipsTabView(generic.ObjectView):
    template_name = 'netbox_relationships/object_relationships.html'
    tab = ViewTab(label=_('Relationships'), badge=edge_count, permission=PERMISSION, weight=2100)

    def get_extra_context(self, request, instance):
        ct = ContentType.objects.get_for_model(instance)
        rows = rows_for(request.user, instance)
        object_key = f'{ct.pk}:{instance.pk}'
        add_many = reverse('plugins:netbox_relationships:relationship_add_many')
        return {
            'base_template': get_default_template(type(instance)),
            'rows': rows,
            'paths': paths.analyse(request.user, (ct.pk, instance.pk)) if rows['needs'] else None,
            'object_key': object_key,
            'add_needs_url': f'{add_many}?object={object_key}&direction=needs&return_url={request.path}',
            'add_needed_by_url': f'{add_many}?object={object_key}&direction=needed_by&return_url={request.path}',
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
