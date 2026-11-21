from netbox.search import SearchIndex

from .models import LogicalService, NetworkTier, Relationship, RelationshipType


class RelationshipTypeIndex(SearchIndex):
    model = RelationshipType
    fields = (
        ('name', 100),
        ('forward_label', 300),
        ('reverse_label', 300),
        ('description', 500),
    )


class RelationshipIndex(SearchIndex):
    model = Relationship
    fields = (
        ('description', 500),
        ('comments', 5000),
    )
    display_attrs = ('type', 'status', 'criticality')


class LogicalServiceIndex(SearchIndex):
    model = LogicalService
    fields = (
        ('name', 100),
        ('description', 500),
        ('comments', 5000),
    )
    display_attrs = ('kind', 'status', 'tenant')


class NetworkTierIndex(SearchIndex):
    model = NetworkTier
    fields = (
        ('name', 100),
        ('description', 500),
    )


indexes = (RelationshipTypeIndex, RelationshipIndex, LogicalServiceIndex, NetworkTierIndex)
