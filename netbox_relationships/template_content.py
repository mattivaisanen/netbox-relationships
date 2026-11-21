"""
What the plugin adds to other NetBox pages:

- a "Relationships" card in the right column of any object's page: how many
  objects it needs and how many need it, the most critical of those, and
  buttons to add a relationship or open the graph;
- an "Impact" button in the page's button bar.
"""
from django.contrib.contenttypes.models import ContentType
from django.urls import NoReverseMatch, reverse

from netbox.plugins import PluginTemplateExtension

from .choices import CriticalityChoices
from .tabs import rows_for, tab_models

PERMISSION = 'netbox_relationships.view_relationship'
_SKIP = {'relationship', 'relationshiptype', 'edgeindex'}
_CRITICALITY_RANK = {value: rank for rank, (value, *_rest) in enumerate(reversed(CriticalityChoices.CHOICES))}


def _applies(context):
    obj = context.get('object')
    request = context.get('request')
    if obj is None or request is None or not getattr(obj, 'pk', None):
        return None
    meta = obj._meta
    if meta.app_label == 'netbox_relationships' and meta.model_name in _SKIP:
        return None
    if not request.user.has_perm(PERMISSION):
        return None
    return obj


def _memo(request, key, compute):
    """compute() once per request (the card and the button share it)."""
    store = request.__dict__.setdefault('_netbox_relationships', {})
    if key not in store:
        store[key] = compute()
    return store[key]


class ObjectRelationships(PluginTemplateExtension):
    models = None

    def right_page(self):
        obj = _applies(self.context)
        if obj is None:
            return ''
        request = self.context['request']
        rows = _memo(request, ('rows', obj._meta.label_lower, obj.pk), lambda: rows_for(request.user, obj))
        ranked = sorted(
            (row for row in rows['needs'] + rows['needed_by'] if not row['other']['hidden']),
            key=lambda row: (not row['manual'], _CRITICALITY_RANK.get(row['criticality_value'], 9)),
        )
        ct = ContentType.objects.get_for_model(obj)
        has_tabs = type(obj) in tab_models()
        object_key = f'{ct.pk}:{obj.pk}'
        add_many = reverse('plugins:netbox_relationships:relationship_add_many')
        all_rows = rows['needs'] + rows['needed_by'] + rows['other']
        return self.render('netbox_relationships/inc/card.html', extra_context={
            'needs_count': len(rows['needs']),
            'needed_by_count': len(rows['needed_by']),
            'other_count': len(rows['other']),
            'derived_count': sum(1 for row in all_rows if not row['manual']),
            'top': ranked[:5],
            'add_needs_url': f'{add_many}?object={object_key}&direction=needs&return_url={request.path}',
            'add_needed_by_url': f'{add_many}?object={object_key}&direction=needed_by&return_url={request.path}',
            'tab_url': _tab_url(obj, 'relationships') if has_tabs else None,
            'graph_url': _tab_url(obj, 'dependency_graph') if has_tabs else None,
            'impact_url': f"{reverse('plugins:netbox_relationships:impact')}?object={object_key}",
            'can_add': request.user.has_perm('netbox_relationships.add_relationship'),
        })

    def buttons(self):
        obj = _applies(self.context)
        if obj is None:
            return ''
        ct = ContentType.objects.get_for_model(obj)
        return self.render('netbox_relationships/inc/impact_button.html', extra_context={
            'impact_url': f"{reverse('plugins:netbox_relationships:impact')}?object={ct.pk}:{obj.pk}",
        })


def _tab_url(obj, name):
    meta = obj._meta
    prefix = 'plugins:' if meta.app_label == 'netbox_relationships' else ''
    try:
        return reverse(f'{prefix}{meta.app_label}:{meta.model_name}_{name}', args=[obj.pk])
    except NoReverseMatch:
        return None


class RelationshipTypeButtons(PluginTemplateExtension):
    """"Add common types" on the relationship types list."""
    models = ['netbox_relationships.relationshiptype']

    def list_buttons(self):
        request = self.context['request']
        if not request.user.has_perm('netbox_relationships.add_relationshiptype'):
            return ''
        return self.render('netbox_relationships/inc/add_common_types.html')


template_extensions = [ObjectRelationships, RelationshipTypeButtons]
