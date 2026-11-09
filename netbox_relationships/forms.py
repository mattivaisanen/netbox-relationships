from django import forms
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Count, Q
from django.utils.translation import gettext_lazy as _

from core.models import ObjectType
from dcim.models import Device, DeviceRole
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
    CSVModelChoiceField, CSVModelMultipleChoiceField, DynamicModelChoiceField, DynamicModelMultipleChoiceField,
    GenericObjectChoiceField, SlugField, TagFilterField,
)
from utilities.forms.mixins import GenericObjectFormMixin
from utilities.forms.rendering import FieldSet
from utilities.forms.widgets import BulkEditNullBooleanSelect

from .choices import (
    CardinalityChoices, CategoryChoices, CriticalityChoices, ImpactChoices, ServiceKindChoices, StatusChoices,
)
from .models import LogicalService, NetworkTier, Relationship, RelationshipType


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
        FieldSet('source', name=_('From (the object that needs)'), html_id='from'),
        FieldSet('type', 'impact', 'label', name=_('Relationship')),
        FieldSet('target', name=_('To (the object that is needed)'), html_id='to'),
        FieldSet('group', 'group_min', name=_('Redundancy')),
        FieldSet('status', 'criticality', 'description', 'tags', name=_('Details')),
    )

    class Meta:
        model = Relationship
        fields = (
            'type', 'impact', 'label', 'group', 'group_min', 'status', 'criticality', 'description', 'owner',
            'comments', 'tags',
        )


class RelationshipBulkEditForm(PrimaryModelBulkEditForm):
    type = DynamicModelChoiceField(label=_('Type'), queryset=RelationshipType.objects.all(), required=False)
    status = forms.ChoiceField(label=_('Status'), choices=add_blank_choice(StatusChoices), required=False)
    criticality = forms.ChoiceField(
        label=_('Criticality'), choices=add_blank_choice(CriticalityChoices), required=False,
    )
    impact = forms.ChoiceField(label=_('Impact'), choices=add_blank_choice(ImpactChoices), required=False)
    label = forms.CharField(label=_('Label'), max_length=100, required=False)
    group = forms.CharField(label=_('Redundancy group'), max_length=50, required=False)
    group_min = forms.IntegerField(label=_('Needs at least'), min_value=1, required=False)
    description = forms.CharField(label=_('Description'), max_length=200, required=False)

    model = Relationship
    fieldsets = (FieldSet('type', 'status', 'criticality', 'impact', 'label', 'group', 'group_min', 'description'),)
    nullable_fields = ('description', 'comments', 'impact', 'label', 'group')


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
    impact = CSVChoiceField(label=_('Impact'), choices=ImpactChoices, required=False,
                            help_text=_("hard, soft or none. Empty: the type's default"))

    class Meta:
        model = Relationship
        fields = (
            'type', 'source_type', 'source_id', 'source_name', 'target_type', 'target_id', 'target_name',
            'status', 'criticality', 'impact', 'label', 'group', 'group_min', 'description', 'owner', 'comments',
            'tags',
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


#
# Adding several relationships at once
#

#: Object pairs where "runs on" is the natural default type.
_HOSTING_PAIRS = {
    ('virtualization.virtualmachine', 'virtualization.cluster'),
    ('virtualization.virtualmachine', 'dcim.device'),
    ('ipam.service', 'virtualization.virtualmachine'),
    ('ipam.service', 'dcim.device'),
    ('netbox_relationships.logicalservice', 'virtualization.virtualmachine'),
    ('netbox_relationships.logicalservice', 'dcim.device'),
    ('netbox_relationships.logicalservice', 'ipam.service'),
}


def types_for(source_ct, target_ct):
    """Relationship types that allow this pair of object types."""
    queryset = RelationshipType.objects.all()
    if source_ct is not None:
        queryset = queryset.filter(Q(source_types__isnull=True) | Q(source_types=source_ct))
    if target_ct is not None:
        queryset = queryset.filter(Q(target_types__isnull=True) | Q(target_types=target_ct))
    return queryset.distinct().order_by('name')


def default_type(source_ct, target_ct, allowed):
    """The type most used for this pair, else "runs on" for hosting pairs, else "depends on"."""
    if source_ct is not None and target_ct is not None:
        used = Relationship.objects.filter(
            source_type=source_ct, target_type=target_ct, type__in=allowed,
        ).values('type').annotate(n=Count('pk')).order_by('-n').first()
        if used:
            return used['type']
        pair = (f'{source_ct.app_label}.{source_ct.model}', f'{target_ct.app_label}.{target_ct.model}')
        preferred = 'runs-on' if pair in _HOSTING_PAIRS else 'depends-on'
        found = allowed.filter(slug=preferred).values_list('pk', flat=True).first()
        if found:
            return found
    return allowed.values_list('pk', flat=True).first()


class EffectChoices:
    """The add form's "if it fails" question, mapped to impact."""
    DEFAULT = ''
    CHOICES = (
        (ImpactChoices.HARD, _('stops working')),
        (ImpactChoices.SOFT, _('works, but worse')),
        (ImpactChoices.NONE, _('is not affected (a note only)')),
        (DEFAULT, _("as the relationship type says")),
    )


class RelationshipAddManyForm(forms.Form):
    """
    One object, a direction ("needs" or "is needed by") and any number of
    other objects of one type: one relationship per other object.
    """
    direction = forms.ChoiceField(
        label=_('This object'), widget=forms.RadioSelect,
        choices=(('needs', _('needs these')), ('needed_by', _('is needed by these'))),
    )
    target_type = forms.ModelChoiceField(label=_('Object type'), queryset=ContentType.objects.none())
    targets = DynamicModelMultipleChoiceField(label=_('Objects'), queryset=Device.objects.none(), required=False)
    type = forms.ModelChoiceField(label=_('Relationship type'), queryset=RelationshipType.objects.none())
    impact = forms.ChoiceField(label=_('If what is needed fails, what needs it'), choices=EffectChoices.CHOICES,
                               required=False, widget=forms.RadioSelect)
    redundant = forms.BooleanField(
        label=_('These back each other up'), required=False,
        help_text=_('Put the new links in one redundancy group, such as two uplinks or two database replicas.'),
    )
    group = forms.CharField(label=_('Group name'), max_length=50, required=False, initial='redundant')
    group_min = forms.IntegerField(label=_('Needs at least'), min_value=1, initial=1, required=False)
    label = forms.CharField(label=_('Label'), max_length=100, required=False,
                            help_text=_('What the links are for, such as "SQL for reporting".'))
    status = forms.ChoiceField(label=_('Status'), choices=StatusChoices, initial=StatusChoices.ACTIVE)
    criticality = forms.ChoiceField(label=_('Criticality'), choices=CriticalityChoices,
                                    initial=CriticalityChoices.MEDIUM)
    description = forms.CharField(label=_('Reason'), max_length=200, required=False)

    def __init__(self, *args, obj=None, target_ct=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.obj = obj
        self.fields['target_type'].queryset = linkable_types()
        self.fields['target_type'].label_from_instance = lambda ct: (
            str(ct.model_class()._meta.verbose_name).capitalize() if ct.model_class() else ct.model
        )
        obj_ct = ContentType.objects.get_for_model(obj) if obj is not None else None
        direction = self.data.get('direction') or self.initial.get('direction') or 'needs'
        source_ct, dest_ct = (obj_ct, target_ct) if direction == 'needs' else (target_ct, obj_ct)
        allowed = types_for(source_ct, dest_ct)
        self.fields['type'].queryset = allowed
        self.fields['type'].initial = default_type(source_ct, dest_ct, allowed)
        if target_ct is not None and target_ct.model_class() is not None:
            model = target_ct.model_class()
            self.fields['targets'].queryset = model.objects.all()
            self.fields['targets'].required = True
        self.fields['impact'].initial = EffectChoices.DEFAULT

    def clean(self):
        data = super().clean()
        if data.get('redundant') and not data.get('group'):
            self.add_error('group', _('Give the group a name.'))
        return data


#
# Network tiers
#

class NetworkTierForm(OrganizationalModelForm):
    slug = SlugField()
    roles = DynamicModelMultipleChoiceField(label=_('Device roles'), queryset=DeviceRole.objects.all(), required=False)

    fieldsets = (
        FieldSet('name', 'slug', 'level', 'roles', 'description', 'tags', name=_('Network tier')),
    )

    class Meta:
        model = NetworkTier
        fields = ('name', 'slug', 'level', 'roles', 'description', 'owner', 'comments', 'tags')

    def clean(self):
        super().clean()
        # A role in two tiers would make cable directions ambiguous.
        roles = self.cleaned_data.get('roles') or []
        taken = NetworkTier.objects.exclude(pk=self.instance.pk).filter(roles__in=roles).values_list(
            'roles__name', 'name').distinct()
        taken = [(role, tier) for role, tier in taken if role in {r.name for r in roles}]
        if taken:
            raise forms.ValidationError({'roles': _('Already in another tier: {list}').format(
                list=', '.join(f'{role} ({tier})' for role, tier in taken))})
        return self.cleaned_data


class NetworkTierImportForm(OrganizationalModelImportForm):
    slug = SlugField()
    roles = CSVModelMultipleChoiceField(
        label=_('Device roles'), queryset=DeviceRole.objects.all(), to_field_name='slug', required=False,
        help_text=_('Role slugs, comma separated'),
    )

    class Meta:
        model = NetworkTier
        fields = ('name', 'slug', 'level', 'roles', 'description', 'owner', 'comments', 'tags')


class NetworkTierFilterForm(OrganizationalModelFilterSetForm):
    model = NetworkTier
    fieldsets = (FieldSet('q', 'filter_id', 'tag'),)
    tag = TagFilterField(model)
