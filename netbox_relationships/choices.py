from django.utils.translation import gettext_lazy as _

from utilities.choices import ChoiceSet


class CategoryChoices(ChoiceSet):
    """What kind of link a relationship type is. Used for filters and the default look."""
    DEPENDENCY = 'dependency'
    HOSTING = 'hosting'
    CONNECTIVITY = 'connectivity'
    DATA_FLOW = 'data_flow'
    OWNERSHIP = 'ownership'
    INFORMATIONAL = 'informational'

    CHOICES = (
        (DEPENDENCY, _('Dependency')),
        (HOSTING, _('Hosting')),
        (CONNECTIVITY, _('Connectivity')),
        (DATA_FLOW, _('Data flow')),
        (OWNERSHIP, _('Ownership')),
        (INFORMATIONAL, _('Informational')),
    )


class ImpactChoices(ChoiceSet):
    """
    What happens to the source of a link when its target fails: it goes down
    (hard), keeps working but worse (soft), or nothing (none).
    """
    HARD = 'hard'
    SOFT = 'soft'
    NONE = 'none'

    CHOICES = (
        (HARD, _('Hard: source goes down'), 'red'),
        (SOFT, _('Soft: source is degraded'), 'orange'),
        (NONE, _('None: informational'), 'gray'),
    )


class CardinalityChoices(ChoiceSet):
    """How many links of one type an object may have."""
    MANY_TO_MANY = 'many_to_many'
    ONE_TO_MANY = 'one_to_many'
    MANY_TO_ONE = 'many_to_one'
    ONE_TO_ONE = 'one_to_one'

    CHOICES = (
        (MANY_TO_MANY, _('Many to many')),
        (ONE_TO_MANY, _('One to many (a target has one source)')),
        (MANY_TO_ONE, _('Many to one (a source has one target)')),
        (ONE_TO_ONE, _('One to one')),
    )


class StatusChoices(ChoiceSet):
    """Status of a relationship or a logical service."""
    key = 'Relationship.status'

    PLANNED = 'planned'
    ACTIVE = 'active'
    DECOMMISSIONING = 'decommissioning'

    CHOICES = [
        (PLANNED, _('Planned'), 'cyan'),
        (ACTIVE, _('Active'), 'green'),
        (DECOMMISSIONING, _('Decommissioning'), 'yellow'),
    ]


class CriticalityChoices(ChoiceSet):
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'
    CRITICAL = 'critical'

    CHOICES = (
        (LOW, _('Low'), 'gray'),
        (MEDIUM, _('Medium'), 'blue'),
        (HIGH, _('High'), 'orange'),
        (CRITICAL, _('Critical'), 'red'),
    )


class ServiceKindChoices(ChoiceSet):
    """What a logical service is. Decides its layer on the service map."""
    BUSINESS_SERVICE = 'business_service'
    APPLICATION = 'application'
    COMPONENT = 'component'
    EXTERNAL = 'external'

    CHOICES = (
        (BUSINESS_SERVICE, _('Business service'), 'purple'),
        (APPLICATION, _('Application'), 'blue'),
        (COMPONENT, _('Component'), 'teal'),
        (EXTERNAL, _('External service'), 'gray'),
    )


class ImpactStateChoices(ChoiceSet):
    """Result of impact analysis for one object. Not stored."""
    FAILED = 'failed'
    DOWN = 'down'
    DEGRADED = 'degraded'
    AT_RISK = 'at_risk'

    CHOICES = (
        (FAILED, _('Failed'), 'black'),
        (DOWN, _('Down'), 'red'),
        (DEGRADED, _('Degraded'), 'orange'),
        (AT_RISK, _('At risk'), 'yellow'),
    )
