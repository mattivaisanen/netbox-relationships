"""
The plugin's models.

- RelationshipType: what a kind of link means (labels, category, impact).
- Relationship: one link, entered by hand, between any two objects.
- LogicalService: a business service, application or external service,
  for things NetBox has no object for.
- EdgeIndex: every link in one narrow table, hand-made and derived from
  NetBox's own data. Internal: it is what graphs and impact analysis read.
"""
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from netbox.models import OrganizationalModel, PrimaryModel
from netbox.models.features import ContactsMixin
from utilities.fields import ColorField

from .choices import (
    CardinalityChoices, CategoryChoices, CriticalityChoices, ImpactChoices, ServiceKindChoices, StatusChoices,
)
from .constants import MANUAL


class RelationshipType(OrganizationalModel):
    """A kind of link, such as "Depends on" or "Runs on"."""
    forward_label = models.CharField(
        verbose_name=_('forward label'), max_length=100,
        help_text=_('Read from source to target, such as "depends on".'),
    )
    reverse_label = models.CharField(
        verbose_name=_('reverse label'), max_length=100,
        help_text=_('Read from target to source, such as "is required by".'),
    )
    category = models.CharField(
        verbose_name=_('category'), max_length=30, choices=CategoryChoices, default=CategoryChoices.DEPENDENCY,
    )
    impact = models.CharField(
        verbose_name=_('impact'), max_length=10, choices=ImpactChoices, default=ImpactChoices.HARD,
        help_text=_('What happens to the source when the target fails.'),
    )
    symmetric = models.BooleanField(
        verbose_name=_('symmetric'), default=False,
        help_text=_('A peer link with no direction. Both ends are treated the same.'),
    )
    allow_cycles = models.BooleanField(
        verbose_name=_('allow loops'), default=False,
        help_text=_('Allow chains of this type that lead back to where they started.'),
    )
    cardinality = models.CharField(
        verbose_name=_('cardinality'), max_length=20, choices=CardinalityChoices,
        default=CardinalityChoices.MANY_TO_MANY,
    )
    source_types = models.ManyToManyField(
        to='contenttypes.ContentType', related_name='+', blank=True, verbose_name=_('source types'),
        help_text=_('Object types allowed as the source. None selected: any.'),
    )
    target_types = models.ManyToManyField(
        to='contenttypes.ContentType', related_name='+', blank=True, verbose_name=_('target types'),
        help_text=_('Object types allowed as the target. None selected: any.'),
    )
    require_description = models.BooleanField(
        verbose_name=_('require a reason'), default=False,
        help_text=_('Every relationship of this type must have a description.'),
    )
    color = ColorField(verbose_name=_('color'), default='6b7690')

    class Meta:
        ordering = ('name',)
        verbose_name = _('relationship type')
        verbose_name_plural = _('relationship types')

    def get_category_color(self):
        return CategoryChoices.colors.get(self.category)

    def get_impact_color(self):
        return ImpactChoices.colors.get(self.impact)


class Relationship(PrimaryModel):
    """One link between two objects of any type, entered by hand."""
    type = models.ForeignKey(
        to=RelationshipType, on_delete=models.PROTECT, related_name='relationships', verbose_name=_('type'),
    )
    source_type = models.ForeignKey(to='contenttypes.ContentType', on_delete=models.CASCADE, related_name='+')
    source_id = models.PositiveBigIntegerField()
    source = GenericForeignKey(ct_field='source_type', fk_field='source_id')
    target_type = models.ForeignKey(to='contenttypes.ContentType', on_delete=models.CASCADE, related_name='+')
    target_id = models.PositiveBigIntegerField()
    target = GenericForeignKey(ct_field='target_type', fk_field='target_id')
    status = models.CharField(
        verbose_name=_('status'), max_length=20, choices=StatusChoices, default=StatusChoices.ACTIVE,
    )
    criticality = models.CharField(
        verbose_name=_('criticality'), max_length=10, choices=CriticalityChoices, default=CriticalityChoices.MEDIUM,
    )

    clone_fields = ('type', 'source_type', 'source_id', 'target_type', 'status', 'criticality')

    class Meta:
        ordering = ('type', 'source_type', 'source_id', 'target_type', 'target_id')
        verbose_name = _('relationship')
        verbose_name_plural = _('relationships')
        constraints = (
            models.UniqueConstraint(
                fields=('type', 'source_type', 'source_id', 'target_type', 'target_id'),
                name='netbox_relationships_relationship_unique',
            ),
        )
        indexes = (
            models.Index(fields=('source_type', 'source_id')),
            models.Index(fields=('target_type', 'target_id')),
        )

    def __str__(self):
        if not self.type_id:
            return super().__str__()
        return f'{self.source} {self.type.forward_label} {self.target}'

    def get_absolute_url(self):
        return reverse('plugins:netbox_relationships:relationship', args=[self.pk])

    def get_status_color(self):
        return StatusChoices.colors.get(self.status)

    def get_criticality_color(self):
        return CriticalityChoices.colors.get(self.criticality)

    def clean(self):
        super().clean()
        # Imported here: validation reads the edge index, which imports models.
        from .validation import relationship_errors
        errors = relationship_errors(self)
        if errors:
            raise ValidationError(errors)


class LogicalService(ContactsMixin, PrimaryModel):
    """A business service, application, component or external service."""
    name = models.CharField(verbose_name=_('name'), max_length=100, unique=True)
    kind = models.CharField(
        verbose_name=_('kind'), max_length=30, choices=ServiceKindChoices, default=ServiceKindChoices.APPLICATION,
    )
    parent = models.ForeignKey(
        to='self', on_delete=models.SET_NULL, related_name='children', blank=True, null=True,
        verbose_name=_('part of'), help_text=_('The business service or application this belongs to.'),
    )
    status = models.CharField(
        verbose_name=_('status'), max_length=20, choices=StatusChoices, default=StatusChoices.ACTIVE,
    )
    criticality = models.CharField(
        verbose_name=_('criticality'), max_length=10, choices=CriticalityChoices, default=CriticalityChoices.MEDIUM,
    )
    tenant = models.ForeignKey(
        to='tenancy.Tenant', on_delete=models.PROTECT, related_name='+', blank=True, null=True,
        verbose_name=_('tenant'),
    )
    link = models.URLField(
        verbose_name=_('link'), max_length=300, blank=True, help_text=_('Where the service lives or is documented.'),
    )

    clone_fields = ('kind', 'parent', 'status', 'criticality', 'tenant')

    class Meta:
        ordering = ('name',)
        verbose_name = _('logical service')
        verbose_name_plural = _('logical services')

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('plugins:netbox_relationships:logicalservice', args=[self.pk])

    def get_kind_color(self):
        return ServiceKindChoices.colors.get(self.kind)

    def get_status_color(self):
        return StatusChoices.colors.get(self.status)

    def get_criticality_color(self):
        return CriticalityChoices.colors.get(self.criticality)

    def clean(self):
        super().clean()
        # A service can't be part of itself, directly or further up.
        node, seen = self.parent, set()
        while node is not None and node.pk not in seen:
            if self.pk and node.pk == self.pk:
                raise ValidationError({'parent': _('A service cannot be part of itself.')})
            seen.add(node.pk)
            node = node.parent


class EdgeIndex(models.Model):
    """
    One link between two objects, as graphs and impact analysis read it.

    Rows with origin "manual" mirror a Relationship. Every other origin is
    the key of an edge provider in derived.py, and `owner` is the object
    whose data the row was worked out from (a VM for "VM runs on cluster",
    a cable for "connects to"), so a change to that object refreshes only
    its rows. Not shown in the UI.
    """
    source_type = models.ForeignKey(to=ContentType, on_delete=models.CASCADE, related_name='+')
    source_id = models.PositiveBigIntegerField()
    target_type = models.ForeignKey(to=ContentType, on_delete=models.CASCADE, related_name='+')
    target_id = models.PositiveBigIntegerField()
    origin = models.CharField(max_length=30, default=MANUAL)
    relationship = models.OneToOneField(
        to=Relationship, on_delete=models.CASCADE, related_name='edge', blank=True, null=True,
    )
    rtype = models.ForeignKey(
        to=RelationshipType, on_delete=models.CASCADE, related_name='+', blank=True, null=True,
    )
    owner_type = models.ForeignKey(to=ContentType, on_delete=models.CASCADE, related_name='+', blank=True, null=True)
    owner_id = models.PositiveBigIntegerField(blank=True, null=True)
    label = models.CharField(max_length=100)
    reverse_label = models.CharField(max_length=100)
    impact = models.CharField(max_length=10, choices=ImpactChoices)
    symmetric = models.BooleanField(default=False)
    status = models.CharField(max_length=20, default=StatusChoices.ACTIVE)
    criticality = models.CharField(max_length=10, default=CriticalityChoices.MEDIUM)
    color = models.CharField(max_length=6, default='6b7690')

    class Meta:
        verbose_name = _('edge')
        verbose_name_plural = _('edges')
        indexes = (
            models.Index(fields=('source_type', 'source_id')),
            models.Index(fields=('target_type', 'target_id')),
            models.Index(fields=('origin', 'owner_type', 'owner_id')),
        )

    def __str__(self):
        return f'{self.source_type_id}:{self.source_id} {self.label} {self.target_type_id}:{self.target_id}'

    @property
    def is_manual(self):
        return self.origin == MANUAL
