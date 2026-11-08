from django.contrib.contenttypes.models import ContentType
from rest_framework import serializers

from netbox.api.fields import ChoiceField, ContentTypeField
from netbox.api.gfk_fields import GFKSerializerField
from netbox.api.serializers import NetBoxModelSerializer
from tenancy.api.serializers import TenantSerializer

from ..choices import (
    CardinalityChoices, CategoryChoices, CriticalityChoices, ImpactChoices, ServiceKindChoices, StatusChoices,
)
from ..forms import linkable_types
from ..models import LogicalService, Relationship, RelationshipType


class RelationshipTypeSerializer(NetBoxModelSerializer):
    category = ChoiceField(choices=CategoryChoices, required=False)
    impact = ChoiceField(choices=ImpactChoices, required=False)
    cardinality = ChoiceField(choices=CardinalityChoices, required=False)
    source_types = ContentTypeField(queryset=ContentType.objects.all(), many=True, required=False)
    target_types = ContentTypeField(queryset=ContentType.objects.all(), many=True, required=False)

    class Meta:
        model = RelationshipType
        fields = (
            'id', 'url', 'display_url', 'display', 'name', 'slug', 'forward_label', 'reverse_label', 'category',
            'impact', 'symmetric', 'allow_cycles', 'cardinality', 'source_types', 'target_types',
            'require_description', 'color', 'description', 'owner', 'comments', 'tags', 'custom_fields',
            'created', 'last_updated',
        )
        brief_fields = ('id', 'url', 'display', 'name', 'slug', 'forward_label', 'reverse_label', 'description')


class RelationshipSerializer(NetBoxModelSerializer):
    type = RelationshipTypeSerializer(nested=True)
    source_type = ContentTypeField(queryset=linkable_types())
    source = GFKSerializerField(read_only=True)
    target_type = ContentTypeField(queryset=linkable_types())
    target = GFKSerializerField(read_only=True)
    status = ChoiceField(choices=StatusChoices, required=False)
    criticality = ChoiceField(choices=CriticalityChoices, required=False)

    class Meta:
        model = Relationship
        fields = (
            'id', 'url', 'display_url', 'display', 'type', 'source_type', 'source_id', 'source', 'target_type',
            'target_id', 'target', 'status', 'criticality', 'description', 'owner', 'comments', 'tags',
            'custom_fields', 'created', 'last_updated',
        )
        brief_fields = ('id', 'url', 'display', 'type', 'source_type', 'source_id', 'target_type', 'target_id')


class LogicalServiceSerializer(NetBoxModelSerializer):
    kind = ChoiceField(choices=ServiceKindChoices, required=False)
    parent = serializers.PrimaryKeyRelatedField(queryset=LogicalService.objects.all(), required=False,
                                                allow_null=True)
    status = ChoiceField(choices=StatusChoices, required=False)
    criticality = ChoiceField(choices=CriticalityChoices, required=False)
    tenant = TenantSerializer(nested=True, required=False, allow_null=True)

    class Meta:
        model = LogicalService
        fields = (
            'id', 'url', 'display_url', 'display', 'name', 'kind', 'parent', 'status', 'criticality', 'tenant',
            'link', 'description', 'owner', 'comments', 'tags', 'custom_fields', 'created', 'last_updated',
        )
        brief_fields = ('id', 'url', 'display', 'name', 'kind', 'description')
