import django_filters
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from netbox.filtersets import OrganizationalModelFilterSet, PrimaryModelFilterSet
from tenancy.filtersets import TenancyFilterSet
from utilities.filters import ContentTypeFilter

from .choices import CategoryChoices, CriticalityChoices, ImpactChoices, ServiceKindChoices, StatusChoices
from .graph import parse_key
from .models import LogicalService, Relationship, RelationshipType


class RelationshipTypeFilterSet(OrganizationalModelFilterSet):
    category = django_filters.MultipleChoiceFilter(choices=CategoryChoices)
    impact = django_filters.MultipleChoiceFilter(choices=ImpactChoices)

    class Meta:
        model = RelationshipType
        fields = ('id', 'name', 'slug', 'symmetric', 'allow_cycles', 'cardinality', 'require_description', 'color')

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(
            Q(name__icontains=value) | Q(forward_label__icontains=value) | Q(reverse_label__icontains=value)
            | Q(description__icontains=value)
        )


class RelationshipFilterSet(PrimaryModelFilterSet):
    type_id = django_filters.ModelMultipleChoiceFilter(queryset=RelationshipType.objects.all(), label=_('Type (ID)'))
    type = django_filters.ModelMultipleChoiceFilter(
        field_name='type__slug', queryset=RelationshipType.objects.all(), to_field_name='slug', label=_('Type (slug)'),
    )
    category = django_filters.MultipleChoiceFilter(field_name='type__category', choices=CategoryChoices)
    status = django_filters.MultipleChoiceFilter(choices=StatusChoices)
    criticality = django_filters.MultipleChoiceFilter(choices=CriticalityChoices)
    impact = django_filters.MultipleChoiceFilter(choices=ImpactChoices)
    source_type = ContentTypeFilter()
    target_type = ContentTypeFilter()
    object = django_filters.CharFilter(
        method='filter_object', label=_('Either end, as "dcim.device:42" or "<content type id>:42"'),
    )

    class Meta:
        model = Relationship
        fields = ('id', 'source_type_id', 'source_id', 'target_type_id', 'target_id', 'label', 'group', 'description')

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(
            Q(description__icontains=value) | Q(comments__icontains=value) | Q(type__name__icontains=value)
            | Q(label__icontains=value)
        )

    def filter_object(self, queryset, name, value):
        parsed = parse_key(value)
        if parsed is None:
            return queryset.none()
        ct_id, pk = parsed
        return queryset.filter(Q(source_type_id=ct_id, source_id=pk) | Q(target_type_id=ct_id, target_id=pk))


class LogicalServiceFilterSet(TenancyFilterSet, PrimaryModelFilterSet):
    kind = django_filters.MultipleChoiceFilter(choices=ServiceKindChoices)
    status = django_filters.MultipleChoiceFilter(choices=StatusChoices)
    criticality = django_filters.MultipleChoiceFilter(choices=CriticalityChoices)
    parent_id = django_filters.ModelMultipleChoiceFilter(
        queryset=LogicalService.objects.all(), label=_('Part of (ID)'),
    )

    class Meta:
        model = LogicalService
        fields = ('id', 'name', 'link', 'description')

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(Q(name__icontains=value) | Q(description__icontains=value))
