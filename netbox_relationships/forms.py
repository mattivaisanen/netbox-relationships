from django import forms
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from django.utils.translation import gettext_lazy as _

from core.models import ObjectType
from netbox.forms import (
    OrganizationalModelBulkEditForm, OrganizationalModelFilterSetForm, OrganizationalModelForm,
    OrganizationalModelImportForm, PrimaryModelBulkEditForm, PrimaryModelFilterSetForm, PrimaryModelForm,
    PrimaryModelImportForm,
)
from tenancy.forms import TenancyFilterForm, TenancyForm
from tenancy.models import Tenant
from utilities.forms import BOOLEAN_WITH_BLANK_CHOICES, add_blank_choice
from utilities.forms.fields import (
    ColorField, CommentField, ContentTypeMultipleChoiceField, CSVChoiceField, CSVContentTypeField,
    CSVModelChoiceField, DynamicModelChoiceField, DynamicModelMultipleChoiceField, GenericObjectChoiceField,
    SlugField, TagFilterField,
)
from utilities.forms.mixins import GenericObjectFormMixin
from utilities.forms.rendering import FieldSet
from utilities.forms.widgets import BulkEditNullBooleanSelect

from .choices import (
    CardinalityChoices, CategoryChoices, CriticalityChoices, ImpactChoices, ServiceKindChoices, StatusChoices,
)
from .models import LogicalService, Relationship, RelationshipType


def linkable_types():
    """
    Object types a relationship can join: NetBox objects with their own
    pages (those that can be bookmarked), this plugin's own left out except
    logical services.
    """
    linkable = ObjectType.objects.with_feature('bookmarks').values('pk')
    return ContentType.objects.filter(pk__in=linkable).exclude(
        app_label='netbox_relationships', model__in=('relationship', 'relationshiptype'),
    ).order_by('app_label', 'model')


#
# Relationship types
#

class RelationshipTypeForm(OrganizationalModelForm):
    slug = SlugField()
    source_types = ContentTypeMultipleChoiceField(
        label=_('Source types'), queryset=ContentType.objects.none(), required=False,
        help_text=_('Leave empty to allow any object.'),
    )
    target_types = ContentTypeMultipleChoiceField(
        label=_('Target types'), queryset=ContentType.objects.none(), required=False,
        help_text=_('Leave empty to allow any object.'),
    )

    fieldsets = (
        FieldSet('name', 'slug', 'forward_label', 'reverse_label', 'color', 'description', 'tags',
                 name=_('Relationship type')),
        FieldSet('category', 'impact', 'symmetric', 'allow_cycles', 'cardinality', 'require_description',
                 name=_('Behaviour')),
        FieldSet('source_types', 'target_types', name=_('Allowed objects')),
    )

    class Meta:
        model = RelationshipType
        fields = (
            'name', 'slug', 'forward_label', 'reverse_label', 'color', 'category', 'impact', 'symmetric',
            'allow_cycles', 'cardinality', 'require_description', 'source_types', 'target_types', 'description',
            'owner', 'comments', 'tags',
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['source_types'].queryset = linkable_types()
        self.fields['target_types'].queryset = linkable_types()


class RelationshipTypeBulkEditForm(OrganizationalModelBulkEditForm):
    category = forms.ChoiceField(label=_('Category'), choices=add_blank_choice(CategoryChoices), required=False)
    impact = forms.ChoiceField(label=_('Impact'), choices=add_blank_choice(ImpactChoices), required=False)
    allow_cycles = forms.NullBooleanField(label=_('Allow loops'), required=False, widget=BulkEditNullBooleanSelect())
    require_description = forms.NullBooleanField(
        label=_('Require a reason'), required=False, widget=BulkEditNullBooleanSelect(),
    )
    color = ColorField(label=_('Color'), required=False)
    description = forms.CharField(label=_('Description'), max_length=200, required=False)

    model = RelationshipType
    fieldsets = (FieldSet('category', 'impact', 'allow_cycles', 'require_description', 'color', 'description'),)
    nullable_fields = ('description',)


class RelationshipTypeImportForm(OrganizationalModelImportForm):
    slug = SlugField()
    category = CSVChoiceField(label=_('Category'), choices=CategoryChoices, required=False)
    impact = CSVChoiceField(label=_('Impact'), choices=ImpactChoices, required=False)
    cardinality = CSVChoiceField(label=_('Cardinality'), choices=CardinalityChoices, required=False)

    class Meta:
        model = RelationshipType
        fields = (
            'name', 'slug', 'forward_label', 'reverse_label', 'category', 'impact', 'symmetric', 'allow_cycles',
            'cardinality', 'require_description', 'color', 'description', 'owner', 'comments', 'tags',
        )


class RelationshipTypeFilterForm(OrganizationalModelFilterSetForm):
    model = RelationshipType
    fieldsets = (
        FieldSet('q', 'filter_id', 'tag'),
        FieldSet('category', 'impact', 'symmetric', 'allow_cycles', name=_('Behaviour')),
    )
    category = forms.MultipleChoiceField(label=_('Category'), choices=CategoryChoices, required=False)
    impact = forms.MultipleChoiceField(label=_('Impact'), choices=ImpactChoices, required=False)
    symmetric = forms.NullBooleanField(
        label=_('Symmetric'), required=False, widget=forms.Select(choices=BOOLEAN_WITH_BLANK_CHOICES),
    )
    allow_cycles = forms.NullBooleanField(
        label=_('Allow loops'), required=False, widget=forms.Select(choices=BOOLEAN_WITH_BLANK_CHOICES),
    )
    tag = TagFilterField(model)


#
# Relationships
#

class RelationshipForm(GenericObjectFormMixin, PrimaryModelForm):
    source = GenericObjectChoiceField(
        label=_('From'), content_type_queryset=linkable_types(), selector=True, hx_target_id='from',
    )
    type = DynamicModelChoiceField(label=_('Type'), queryset=RelationshipType.objects.all())
    target = GenericObjectChoiceField(
        label=_('To'), content_type_queryset=linkable_types(), selector=True, hx_target_id='to',
    )
    comments = CommentField()

    fieldsets = (
        FieldSet('source', name=_('From'), html_id='from'),
        FieldSet('type', name=_('Relationship')),
        FieldSet('target', name=_('To'), html_id='to'),
        FieldSet('status', 'criticality', 'description', 'tags', name=_('Details')),
    )

    class Meta:
        model = Relationship
        fields = ('type', 'status', 'criticality', 'description', 'owner', 'comments', 'tags')


class RelationshipBulkEditForm(PrimaryModelBulkEditForm):
    type = DynamicModelChoiceField(label=_('Type'), queryset=RelationshipType.objects.all(), required=False)
    status = forms.ChoiceField(label=_('Status'), choices=add_blank_choice(StatusChoices), required=False)
    criticality = forms.ChoiceField(
        label=_('Criticality'), choices=add_blank_choice(CriticalityChoices), required=False,
    )
    description = forms.CharField(label=_('Description'), max_length=200, required=False)

    model = Relationship
    fieldsets = (FieldSet('type', 'status', 'criticality', 'description'),)
    nullable_fields = ('description', 'comments')


class _ObjectByNameMixin:
    """
    Import columns for one end: `<end>_type` plus `<end>_id` or
    `<end>_name` (looked up by the model's name field).
    """

    def _resolve_end(self, end):
        data = self.cleaned_data
        content_type = data.get(f'{end}_type')
        pk, name = data.get(f'{end}_id'), data.get(f'{end}_name')
        if content_type is None:
            return
        model = content_type.model_class()
        if pk:
            if not model.objects.filter(pk=pk).exists():
                self.add_error(f'{end}_id', _('No such object.'))
            return
        if not name:
            self.add_error(f'{end}_name', _('Give an ID or a name.'))
            return
        try:
            data[f'{end}_id'] = model.objects.get(name=name).pk
        except (ObjectDoesNotExist, model.MultipleObjectsReturned, Exception):
            self.add_error(f'{end}_name', _('No single {type} named "{name}".').format(
                type=model._meta.verbose_name, name=name,
            ))


class RelationshipImportForm(_ObjectByNameMixin, PrimaryModelImportForm):
    type = CSVModelChoiceField(
        label=_('Type'), queryset=RelationshipType.objects.all(), to_field_name='slug',
        help_text=_('Slug of the relationship type'),
    )
    source_type = CSVContentTypeField(
        label=_('Source type'), queryset=ContentType.objects.all(), help_text=_('Such as dcim.device'),
    )
    source_id = forms.IntegerField(label=_('Source ID'), required=False)
    source_name = forms.CharField(label=_('Source name'), required=False, help_text=_('Used when no ID is given'))
    target_type = CSVContentTypeField(
        label=_('Target type'), queryset=ContentType.objects.all(), help_text=_('Such as ipam.service'),
    )
    target_id = forms.IntegerField(label=_('Target ID'), required=False)
    target_name = forms.CharField(label=_('Target name'), required=False, help_text=_('Used when no ID is given'))
    status = CSVChoiceField(label=_('Status'), choices=StatusChoices, required=False)
    criticality = CSVChoiceField(label=_('Criticality'), choices=CriticalityChoices, required=False)

    class Meta:
        model = Relationship
        fields = (
            'type', 'source_type', 'source_id', 'source_name', 'target_type', 'target_id', 'target_name',
            'status', 'criticality', 'description', 'owner', 'comments', 'tags',
        )

    def clean(self):
        super().clean()
        self._resolve_end('source')
        self._resolve_end('target')
        for end in ('source', 'target'):
            if self.cleaned_data.get(f'{end}_id'):
                setattr(self.instance, f'{end}_id', self.cleaned_data[f'{end}_id'])
        return self.cleaned_data


class RelationshipFilterForm(PrimaryModelFilterSetForm):
    model = Relationship
    fieldsets = (
        FieldSet('q', 'filter_id', 'tag'),
        FieldSet('type_id', 'category', 'status', 'criticality', name=_('Relationship')),
        FieldSet('source_type', 'target_type', name=_('Ends')),
    )
    type_id = DynamicModelMultipleChoiceField(
        label=_('Type'), queryset=RelationshipType.objects.all(), required=False,
    )
    category = forms.MultipleChoiceField(label=_('Category'), choices=CategoryChoices, required=False)
    status = forms.MultipleChoiceField(label=_('Status'), choices=StatusChoices, required=False)
    criticality = forms.MultipleChoiceField(label=_('Criticality'), choices=CriticalityChoices, required=False)
    source_type = forms.ChoiceField(label=_('Source type'), required=False)
    target_type = forms.ChoiceField(label=_('Target type'), required=False)
    tag = TagFilterField(model)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        choices = [('', '---------')] + [
            (f'{ct.app_label}.{ct.model}', str(ct.model_class()._meta.verbose_name).capitalize())
            for ct in linkable_types() if ct.model_class() is not None
        ]
        self.fields['source_type'].choices = choices
        self.fields['target_type'].choices = choices


#
# Logical services
#

class LogicalServiceForm(TenancyForm, PrimaryModelForm):
    parent = DynamicModelChoiceField(label=_('Part of'), queryset=LogicalService.objects.all(), required=False)
    comments = CommentField()

    fieldsets = (
        FieldSet('name', 'kind', 'parent', 'status', 'criticality', 'link', 'description', 'tags',
                 name=_('Logical service')),
        FieldSet('tenant_group', 'tenant', name=_('Tenancy')),
    )

    class Meta:
        model = LogicalService
        fields = (
            'name', 'kind', 'parent', 'status', 'criticality', 'link', 'tenant_group', 'tenant', 'description',
            'owner', 'comments', 'tags',
        )


class LogicalServiceBulkEditForm(PrimaryModelBulkEditForm):
    kind = forms.ChoiceField(label=_('Kind'), choices=add_blank_choice(ServiceKindChoices), required=False)
    parent = DynamicModelChoiceField(label=_('Part of'), queryset=LogicalService.objects.all(), required=False)
    status = forms.ChoiceField(label=_('Status'), choices=add_blank_choice(StatusChoices), required=False)
    criticality = forms.ChoiceField(
        label=_('Criticality'), choices=add_blank_choice(CriticalityChoices), required=False,
    )
    tenant = DynamicModelChoiceField(label=_('Tenant'), queryset=Tenant.objects.all(), required=False)
    description = forms.CharField(label=_('Description'), max_length=200, required=False)

    model = LogicalService
    fieldsets = (FieldSet('kind', 'parent', 'status', 'criticality', 'tenant', 'description'),)
    nullable_fields = ('parent', 'tenant', 'description', 'comments')


class LogicalServiceImportForm(PrimaryModelImportForm):
    kind = CSVChoiceField(label=_('Kind'), choices=ServiceKindChoices, required=False)
    parent = CSVModelChoiceField(
        label=_('Part of'), queryset=LogicalService.objects.all(), to_field_name='name', required=False,
    )
    status = CSVChoiceField(label=_('Status'), choices=StatusChoices, required=False)
    criticality = CSVChoiceField(label=_('Criticality'), choices=CriticalityChoices, required=False)
    tenant = CSVModelChoiceField(label=_('Tenant'), queryset=Tenant.objects.all(), to_field_name='name',
                                 required=False)

    class Meta:
        model = LogicalService
        fields = (
            'name', 'kind', 'parent', 'status', 'criticality', 'tenant', 'link', 'description', 'owner',
            'comments', 'tags',
        )


class LogicalServiceFilterForm(TenancyFilterForm, PrimaryModelFilterSetForm):
    model = LogicalService
    fieldsets = (
        FieldSet('q', 'filter_id', 'tag'),
        FieldSet('kind', 'parent_id', 'status', 'criticality', name=_('Service')),
        FieldSet('tenant_group_id', 'tenant_id', name=_('Tenancy')),
    )
    kind = forms.MultipleChoiceField(label=_('Kind'), choices=ServiceKindChoices, required=False)
    parent_id = DynamicModelMultipleChoiceField(
        label=_('Part of'), queryset=LogicalService.objects.all(), required=False,
    )
    status = forms.MultipleChoiceField(label=_('Status'), choices=StatusChoices, required=False)
    criticality = forms.MultipleChoiceField(label=_('Criticality'), choices=CriticalityChoices, required=False)
    tag = TagFilterField(model)


#
# Impact analysis
#

class ImpactAddForm(forms.Form):
    """Adds one object to the impact analysis by type and name."""
    object_type = forms.ModelChoiceField(label=_('Object type'), queryset=ContentType.objects.none(), required=False)
    name = forms.CharField(label=_('Name'), required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['object_type'].queryset = linkable_types()
        self.fields['object_type'].label_from_instance = lambda ct: (
            str(ct.model_class()._meta.verbose_name).capitalize() if ct.model_class() else ct.model
        )
