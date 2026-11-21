"""
Optional integration with netbox-change-approval.

With that plugin installed, a new relationship is saved at once and its
change request stays pending until someone approves it. Such a link is
real in the database but not yet agreed, so:

- impact analysis and "path to the top" leave it out;
- graphs show it, marked as pending approval.

Nothing here imports change-approval at module level: the plugin may not be
installed, and its models are only looked up when a query needs them.
"""
import logging

from django.apps import apps
from django.contrib.contenttypes.models import ContentType

logger = logging.getLogger('netbox_relationships.integrations')

CHANGE_APPROVAL = 'netbox_change_approval'


def has_change_approval():
    """True when netbox-change-approval is installed."""
    return apps.is_installed(CHANGE_APPROVAL)


def pending_relationship_ids():
    """
    A queryset of the ids of relationships whose creation still waits for
    approval, for use in `relationship_id__in=...` (one subquery, not a
    list). None when change-approval is not installed or can't be read.
    """
    if not has_change_approval():
        return None
    try:
        from .models import Relationship

        change_request = apps.get_model(CHANGE_APPROVAL, 'ChangeRequest')
        return change_request.objects.filter(
            content_type_id=ContentType.objects.get_for_model(Relationship).pk,
            action='create',
            status='pending',
            object_id__isnull=False,
        ).values('object_id')
    except Exception:
        # A change-approval version with other names: treat nothing as
        # pending rather than break graphs and impact analysis.
        logger.exception('Could not read pending relationships from netbox-change-approval')
        return None
