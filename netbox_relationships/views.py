from django.contrib import messages
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.utils.translation import ngettext
from django.views.generic import View

from netbox.views import generic
from utilities.views import ConditionalLoginRequiredMixin, register_model_view

from . import filtersets, forms, impact, servicemap, settings, tables, tabs
from .choices import ImpactChoices
from .constants import COMMON_TYPES, MANUAL
from .edges import rebuild
from .graph import EDGE_FIELDS, key, parse_key, resolve
from .models import EdgeIndex, LogicalService, Relationship, RelationshipType

#
# Relationship types
#


@register_model_view(RelationshipType, 'list', path='', detail=False)
class RelationshipTypeListView(generic.ObjectListView):
    queryset = RelationshipType.objects.prefetch_related('source_types', 'target_types', 'tags')
    filterset = filtersets.RelationshipTypeFilterSet
    filterset_form = forms.RelationshipTypeFilterForm
    table = tables.RelationshipTypeTable


@register_model_view(RelationshipType)
class RelationshipTypeView(generic.ObjectView):
    queryset = RelationshipType.objects.all()

    def get_extra_context(self, request, instance):
        relationships = Relationship.objects.restrict(request.user, 'view').filter(type=instance)
        table = tables.RelationshipTable(relationships[:25], exclude=('type',))
        table.configure(request)
        return {'relationship_count': relationships.count(), 'relationships_table': table}


@register_model_view(RelationshipType, 'add', detail=False)
@register_model_view(RelationshipType, 'edit')
class RelationshipTypeEditView(generic.ObjectEditView):
    queryset = RelationshipType.objects.all()
    form = forms.RelationshipTypeForm


@register_model_view(RelationshipType, 'delete')
class RelationshipTypeDeleteView(generic.ObjectDeleteView):
    queryset = RelationshipType.objects.all()


@register_model_view(RelationshipType, 'bulk_import', path='import', detail=False)
class RelationshipTypeBulkImportView(generic.BulkImportView):
    queryset = RelationshipType.objects.all()
    model_form = forms.RelationshipTypeImportForm


@register_model_view(RelationshipType, 'bulk_edit', path='edit', detail=False)
class RelationshipTypeBulkEditView(generic.BulkEditView):
    queryset = RelationshipType.objects.all()
    filterset = filtersets.RelationshipTypeFilterSet
    table = tables.RelationshipTypeTable
    form = forms.RelationshipTypeBulkEditForm


@register_model_view(RelationshipType, 'bulk_delete', path='delete', detail=False)
class RelationshipTypeBulkDeleteView(generic.BulkDeleteView):
    queryset = RelationshipType.objects.all()
    filterset = filtersets.RelationshipTypeFilterSet
    table = tables.RelationshipTypeTable


#
# Relationships
#

@register_model_view(Relationship, 'list', path='', detail=False)
class RelationshipListView(generic.ObjectListView):
    queryset = Relationship.objects.select_related('type', 'source_type', 'target_type').prefetch_related('tags')
    filterset = filtersets.RelationshipFilterSet
    filterset_form = forms.RelationshipFilterForm
    table = tables.RelationshipTable


@register_model_view(Relationship)
class RelationshipView(generic.ObjectView):
    queryset = Relationship.objects.select_related('type')


@register_model_view(Relationship, 'add', detail=False)
@register_model_view(Relationship, 'edit')
class RelationshipEditView(generic.ObjectEditView):
    queryset = Relationship.objects.all()
    form = forms.RelationshipForm


@register_model_view(Relationship, 'delete')
class RelationshipDeleteView(generic.ObjectDeleteView):
    queryset = Relationship.objects.all()


@register_model_view(Relationship, 'bulk_import', path='import', detail=False)
class RelationshipBulkImportView(generic.BulkImportView):
    queryset = Relationship.objects.all()
    model_form = forms.RelationshipImportForm


@register_model_view(Relationship, 'bulk_edit', path='edit', detail=False)
class RelationshipBulkEditView(generic.BulkEditView):
    queryset = Relationship.objects.all()
    filterset = filtersets.RelationshipFilterSet
    table = tables.RelationshipTable
    form = forms.RelationshipBulkEditForm


@register_model_view(Relationship, 'bulk_delete', path='delete', detail=False)
class RelationshipBulkDeleteView(generic.BulkDeleteView):
    queryset = Relationship.objects.all()
    filterset = filtersets.RelationshipFilterSet
    table = tables.RelationshipTable


#
# Logical services
#

@register_model_view(LogicalService, 'list', path='', detail=False)
class LogicalServiceListView(generic.ObjectListView):
    queryset = LogicalService.objects.select_related('parent', 'tenant').prefetch_related('tags')
    filterset = filtersets.LogicalServiceFilterSet
    filterset_form = forms.LogicalServiceFilterForm
    table = tables.LogicalServiceTable


@register_model_view(LogicalService)
class LogicalServiceView(generic.ObjectView):
    queryset = LogicalService.objects.select_related('parent', 'tenant')

    def get_extra_context(self, request, instance):
        children = LogicalService.objects.restrict(request.user, 'view').filter(parent=instance)
        table = tables.LogicalServiceTable(children, exclude=('parent',))
        table.configure(request)
        return {'children_table': table}


@register_model_view(LogicalService, 'add', detail=False)
@register_model_view(LogicalService, 'edit')
class LogicalServiceEditView(generic.ObjectEditView):
    queryset = LogicalService.objects.all()
    form = forms.LogicalServiceForm


@register_model_view(LogicalService, 'delete')
class LogicalServiceDeleteView(generic.ObjectDeleteView):
    queryset = LogicalService.objects.all()


@register_model_view(LogicalService, 'bulk_import', path='import', detail=False)
class LogicalServiceBulkImportView(generic.BulkImportView):
    queryset = LogicalService.objects.all()
    model_form = forms.LogicalServiceImportForm


@register_model_view(LogicalService, 'bulk_edit', path='edit', detail=False)
class LogicalServiceBulkEditView(generic.BulkEditView):
    queryset = LogicalService.objects.all()
    filterset = filtersets.LogicalServiceFilterSet
    table = tables.LogicalServiceTable
    form = forms.LogicalServiceBulkEditForm


@register_model_view(LogicalService, 'bulk_delete', path='delete', detail=False)
class LogicalServiceBulkDeleteView(generic.BulkDeleteView):
    queryset = LogicalService.objects.all()
    filterset = filtersets.LogicalServiceFilterSet
    table = tables.LogicalServiceTable


#
# Impact analysis and service map
#

def _objects_from(request, param='object'):
    """(ct, pk) pairs from repeated ?object=<ct>:<pk> parameters."""
    found = []
    for value in request.GET.getlist(param):
        parsed = parse_key(value)
        if parsed and parsed not in found:
            found.append(parsed)
    return found


class ImpactView(ConditionalLoginRequiredMixin, View):
    """Pick objects, see what fails with them. Everything travels in the URL, so a result can be shared."""
    template_name = 'netbox_relationships/impact.html'

    def get(self, request):
        objects = _objects_from(request)
        add_form = forms.ImpactAddForm(request.GET or None)
        # "Add" resolves a type and a name to one more object.
        if add_form.is_valid() and add_form.cleaned_data.get('object_type') and add_form.cleaned_data.get('name'):
            content_type = add_form.cleaned_data['object_type']
            model = content_type.model_class()
            queryset = model.objects.restrict(request.user, 'view') if hasattr(model.objects, 'restrict') else \
                model.objects.all()
            name = add_form.cleaned_data['name'].strip()
            match = None
            if hasattr(model, 'name'):
                match = queryset.filter(name__iexact=name).first()
            if match is None:
                messages.warning(request, _('No {type} named "{name}".').format(
                    type=model._meta.verbose_name, name=name,
                ))
            elif (content_type.pk, match.pk) not in objects:
                objects.append((content_type.pk, match.pk))
            add_form = forms.ImpactAddForm()

        scenario = 'maintenance' if request.GET.get('scenario') == 'maintenance' else 'failure'
        planned = request.GET.get('planned')
        include_planned = settings.get('include_planned_in_impact') if planned is None else planned == 'on'
        result = impact.analyse(request.user, objects, include_planned=include_planned) if objects else None
        keys = [key(*obj) for obj in objects]
        return render(request, self.template_name, {
            'add_form': add_form,
            'object_keys': keys,
            'scenario': scenario,
            'include_planned': include_planned,
            'result': result,
            'query': '&'.join(f'object={k}' for k in keys),
        })


class ServiceMapView(ConditionalLoginRequiredMixin, View):
    """Logical services and what they stand on, one band per layer."""
    template_name = 'netbox_relationships/servicemap.html'

    def get(self, request):
        service = None
        if request.GET.get('service'):
            service = LogicalService.objects.restrict(request.user, 'view').filter(
                pk=request.GET.get('service')).first()
        failed = _objects_from(request, 'failed')
        states, result = {}, None
        if failed:
            result = impact.analyse(request.user, failed)
            for node in result['failed'] + result['affected']:
                states[parse_key(node['id'])] = node.get('state', 'failed')
        data = servicemap.build(request.user, service=service, states=states)
        return render(request, self.template_name, {
            'map': data,
            'service': service,
            'services': LogicalService.objects.restrict(request.user, 'view').filter(parent__isnull=True),
            'result': result,
            'failed_query': '&'.join(f'failed={key(*obj)}' for obj in failed),
            'object_query': '&'.join(f'object={key(*obj)}' for obj in failed),
        })


#
# Adding several relationships at once
#

def _object_from(request, value):
    """The object behind "<ct>:<pk>" if the user may view it, else None."""
    parsed = parse_key(value or '')
    if parsed is None:
        return None
    model = ContentType.objects.get_for_id(parsed[0]).model_class()
    if model is None:
        return None
    queryset = model.objects.all()
    if hasattr(queryset, 'restrict'):
        queryset = queryset.restrict(request.user, 'view')
    return queryset.filter(pk=parsed[1]).first()


class RelationshipAddManyView(ConditionalLoginRequiredMixin, View):
    """
    Links one object to several others in one go: "this object needs these"
    or "these need this object". One relationship per other object, all in
    one transaction (and one change log request).
    """
    template_name = 'netbox_relationships/relationship_add_many.html'

    def _context(self, request):
        obj = _object_from(request, request.GET.get('object') or request.POST.get('object'))
        target_ct = None
        type_id = request.GET.get('target_type') or request.POST.get('target_type')
        if type_id and str(type_id).isdigit():
            target_ct = ContentType.objects.filter(pk=type_id).first()
        return obj, target_ct

    def _render(self, request, form, obj, target_ct):
        return render(request, self.template_name, {
            'form': form, 'obj': obj, 'target_ct': target_ct,
            'object_key': key(ContentType.objects.get_for_model(obj).pk, obj.pk),
            'return_url': safe_return_url(request, obj),
            'version': tabs.asset_version(),
        })

    def get(self, request):
        if not request.user.has_perm('netbox_relationships.add_relationship'):
            return HttpResponseForbidden()
        obj, target_ct = self._context(request)
        if obj is None:
            messages.warning(request, _('Open this page from an object: its Relationships card or tab.'))
            return redirect('plugins:netbox_relationships:relationship_list')
        form = forms.RelationshipAddManyForm(obj=obj, target_ct=target_ct, initial={
            'direction': request.GET.get('direction', 'needs'), 'target_type': target_ct,
        })
        return self._render(request, form, obj, target_ct)

    def post(self, request):
        if not request.user.has_perm('netbox_relationships.add_relationship'):
            return HttpResponseForbidden()
        obj, target_ct = self._context(request)
        if obj is None:
            return HttpResponseForbidden()
        form = forms.RelationshipAddManyForm(request.POST, obj=obj, target_ct=target_ct)
        if not form.is_valid():
            return self._render(request, form, obj, target_ct)
        data = form.cleaned_data
        targets = data['targets']
        if hasattr(targets, 'restrict'):
            targets = targets.restrict(request.user, 'view')
        created, skipped, errors = [], [], []
        try:
            with transaction.atomic():
                for other in targets:
                    source, target = (obj, other) if data['direction'] == 'needs' else (other, obj)
                    rel = Relationship(
                        type=data['type'], source=source, target=target, status=data['status'],
                        criticality=data['criticality'], impact=data['impact'] or '', label=data['label'],
                        description=data['description'],
                        group=data['group'] if data['redundant'] else '',
                        group_min=(data['group_min'] or 1) if data['redundant'] else 1,
                    )
                    if Relationship.objects.filter(
                            type=rel.type, source_type=rel.source_type, source_id=rel.source_id,
                            target_type=rel.target_type, target_id=rel.target_id).exists():
                        skipped.append(str(other))
                        continue
                    try:
                        rel.full_clean()
                    except ValidationError as error:
                        errors.append(f"{other}: {'; '.join(error.messages)}")
                        continue
                    rel.save()
                    created.append(rel)
                if errors:
                    raise ValidationError(errors)
        except ValidationError:
            for message in errors:
                form.add_error(None, message)
            return self._render(request, form, obj, target_ct)
        if created:
            messages.success(request, ngettext(
                'Added %(n)d relationship.', 'Added %(n)d relationships.', len(created)) % {'n': len(created)})
        if skipped:
            messages.info(request, _('Already linked, left as they are: {names}').format(names=', '.join(skipped)))
        return redirect(safe_return_url(request, obj))


def safe_return_url(request, obj):
    """The return_url parameter when it is a local path, else the object's page."""
    url = request.GET.get('return_url') or request.POST.get('return_url')
    if url and url_has_allowed_host_and_scheme(url, allowed_hosts=None) and url.startswith('/'):
        return url
    return obj.get_absolute_url()


#
# Every link, manual and derived
#

class LinkListView(ConditionalLoginRequiredMixin, View):
    """
    Every link in the index, hand-made and worked out from NetBox, with its
    origin. Read only: hand-made links are edited from Relationships, the
    others by changing the NetBox data they come from.
    """
    template_name = 'netbox_relationships/link_list.html'
    per_page = 50

    def get(self, request):
        if not request.user.has_perm('netbox_relationships.view_relationship'):
            return HttpResponseForbidden()
        queryset = EdgeIndex.objects.order_by('origin', 'pk')
        origin = request.GET.get('origin')
        if origin:
            queryset = queryset.filter(origin=origin)
        impacting = request.GET.get('impact')
        if impacting in ('hard', 'soft', 'none'):
            queryset = queryset.filter(impact=impacting)
        counts = dict(EdgeIndex.objects.values_list('origin').annotate(n=Count('pk')).values_list('origin', 'n'))
        page = Paginator(queryset.values(*EDGE_FIELDS), self.per_page).get_page(request.GET.get('page'))
        rows = list(page.object_list)
        ends = {(r['source_type_id'], r['source_id']) for r in rows}
        ends |= {(r['target_type_id'], r['target_id']) for r in rows}
        nodes = resolve(request.user, ends)
        links = [{
            'source': nodes[(r['source_type_id'], r['source_id'])],
            'target': nodes[(r['target_type_id'], r['target_id'])],
            'label': r['label'], 'note': r['note'], 'symmetric': r['symmetric'],
            'impact': tabs.choice(ImpactChoices, r['impact']),
            'group': r['group'], 'group_min': r['group_min'], 'link_count': r['link_count'],
            'manual': r['origin'] == MANUAL, 'origin': tabs.ORIGIN_LABELS.get(r['origin'], r['origin']),
            'relationship_id': r['relationship_id'],
        } for r in rows]
        origins = sorted(
            ((value, tabs.ORIGIN_LABELS.get(value, value), n) for value, n in counts.items()),
            key=lambda item: (item[0] != MANUAL, str(item[1])),
        )
        query = request.GET.copy()
        query.pop('page', None)
        return render(request, self.template_name, {
            'links': links, 'page': page, 'origins': origins, 'origin': origin, 'impact': impacting,
            'total': sum(counts.values()), 'query': query.urlencode(),
            'can_rebuild': request.user.has_perm('netbox_relationships.change_relationship'),
        })


class RebuildIndexView(ConditionalLoginRequiredMixin, View):
    """Rebuilds the whole index now (the same as the nightly job)."""

    def post(self, request):
        if not request.user.has_perm('netbox_relationships.change_relationship'):
            return HttpResponseForbidden()
        counts = rebuild()
        messages.success(request, ngettext(
            'Rebuilt: %(n)d link.', 'Rebuilt: %(n)d links.', sum(counts.values())) % {'n': sum(counts.values())})
        return redirect('plugins:netbox_relationships:link_list')


class AddCommonTypesView(ConditionalLoginRequiredMixin, View):
    """Creates the optional common relationship types that don't exist yet. Never changes existing ones."""

    def post(self, request):
        if not request.user.has_perm('netbox_relationships.add_relationshiptype'):
            return HttpResponseForbidden()
        added = []
        for name, slug, forward, reverse, category, impact_value, symmetric, color in COMMON_TYPES:
            if RelationshipType.objects.filter(Q(slug=slug) | Q(name=name)).exists():
                continue
            rtype = RelationshipType(
                name=name, slug=slug, forward_label=forward, reverse_label=reverse, category=category,
                impact=impact_value, symmetric=symmetric, allow_cycles=symmetric, color=color,
            )
            rtype.full_clean()
            rtype.save()
            added.append(name)
        if added:
            messages.success(request, _('Added: {names}').format(names=', '.join(added)))
        else:
            messages.info(request, _('All common types are already there.'))
        return redirect('plugins:netbox_relationships:relationshiptype_list')
