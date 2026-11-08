from django.contrib import messages
from django.shortcuts import render
from django.utils.translation import gettext as _
from django.views.generic import View

from netbox.views import generic
from utilities.views import ConditionalLoginRequiredMixin, register_model_view

from . import filtersets, forms, impact, servicemap, settings, tables
from .graph import key, parse_key
from .models import LogicalService, Relationship, RelationshipType

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
