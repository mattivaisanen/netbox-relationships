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
        needs = rows['needs'] + rows['derived_needs']
        needed_by = rows['needed_by'] + rows['derived_needed_by']
        top = sorted(
            (row for row in needed_by if not row['other']['hidden']),
            key=lambda row: _CRITICALITY_RANK.get(row['criticality_value'], 9),
        )[:3]
        ct = ContentType.objects.get_for_model(obj)
        has_tabs = type(obj) in tab_models()
        return self.render('netbox_relationships/inc/card.html', extra_context={
            'needs_count': len(needs),
            'needed_by_count': len(needed_by),
            'top': top,
            'add_url': (
                f"{reverse('plugins:netbox_relationships:relationship_add')}"
                f"?source_content_type={ct.pk}&source_object_id={obj.pk}&return_url={request.path}"
            ),
            'graph_url': _tab_url(obj, 'dependency_graph') if has_tabs else None,
            'impact_url': f"{reverse('plugins:netbox_relationships:impact')}?object={ct.pk}:{obj.pk}",
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


template_extensions = [ObjectRelationships]
