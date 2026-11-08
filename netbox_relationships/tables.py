import django_tables2 as tables
from django.utils.translation import gettext_lazy as _

from netbox.tables import OrganizationalModelTable, PrimaryModelTable, columns
from tenancy.tables import TenancyColumnsMixin

from .models import LogicalService, Relationship, RelationshipType


class RelationshipTypeTable(OrganizationalModelTable):
    name = tables.Column(linkify=True)
    color = columns.ColorColumn()
    category = columns.ChoiceFieldColumn()
    impact = columns.ChoiceFieldColumn()
    symmetric = columns.BooleanColumn()
    allow_cycles = columns.BooleanColumn(verbose_name=_('Loops'))
    require_description = columns.BooleanColumn(verbose_name=_('Reason required'))
    source_types = columns.ContentTypesColumn()
    target_types = columns.ContentTypesColumn()
    relationships = columns.LinkedCountColumn(
        viewname='plugins:netbox_relationships:relationship_list', url_params={'type_id': 'pk'},
        verbose_name=_('Relationships'),
    )
    tags = columns.TagColumn(url_name='plugins:netbox_relationships:relationshiptype_list')

    class Meta(OrganizationalModelTable.Meta):
        model = RelationshipType
        fields = (
            'pk', 'id', 'name', 'slug', 'forward_label', 'reverse_label', 'color', 'category', 'impact',
            'symmetric', 'allow_cycles', 'cardinality', 'require_description', 'source_types', 'target_types',
            'relationships', 'description', 'tags', 'created', 'last_updated',
        )
        default_columns = ('pk', 'name', 'forward_label', 'reverse_label', 'category', 'impact', 'relationships')


class RelationshipTable(PrimaryModelTable):
    id = tables.Column(linkify=True, verbose_name=_('ID'))
    source_type = columns.ContentTypeColumn(verbose_name=_('Source type'))
    source = tables.Column(linkify=True, orderable=False, verbose_name=_('Source'))
    type = tables.Column(linkify=True, verbose_name=_('Type'))
    label = tables.Column(
        accessor='type__forward_label', verbose_name=_('Relationship'),
        linkify=lambda record: record.get_absolute_url(),
    )
    target_type = columns.ContentTypeColumn(verbose_name=_('Target type'))
    target = tables.Column(linkify=True, orderable=False, verbose_name=_('Target'))
    status = columns.ChoiceFieldColumn()
    criticality = columns.ChoiceFieldColumn()
    tags = columns.TagColumn(url_name='plugins:netbox_relationships:relationship_list')

    class Meta(PrimaryModelTable.Meta):
        model = Relationship
        fields = (
            'pk', 'id', 'source_type', 'source', 'label', 'type', 'target_type', 'target', 'status',
            'criticality', 'description', 'tags', 'created', 'last_updated',
        )
        default_columns = ('pk', 'source', 'label', 'target', 'target_type', 'status', 'criticality', 'description')


class LogicalServiceTable(TenancyColumnsMixin, PrimaryModelTable):
    name = tables.Column(linkify=True)
    kind = columns.ChoiceFieldColumn()
    parent = tables.Column(linkify=True, verbose_name=_('Part of'))
    status = columns.ChoiceFieldColumn()
    criticality = columns.ChoiceFieldColumn()
    link = tables.TemplateColumn(
        template_code='{% if value %}<a href="{{ value }}">{{ value }}</a>{% endif %}', verbose_name=_('Link'),
    )
    tags = columns.TagColumn(url_name='plugins:netbox_relationships:logicalservice_list')

    class Meta(PrimaryModelTable.Meta):
        model = LogicalService
        fields = (
            'pk', 'id', 'name', 'kind', 'parent', 'status', 'criticality', 'tenant', 'tenant_group', 'link',
            'description', 'tags', 'created', 'last_updated',
        )
        default_columns = ('pk', 'name', 'kind', 'parent', 'status', 'criticality', 'tenant')
