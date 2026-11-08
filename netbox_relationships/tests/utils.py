"""Small helpers that build NetBox objects for the tests."""
from django.contrib.auth import get_user_model

from dcim.models import Device, DeviceRole, DeviceType, Manufacturer, Site

from ..models import Relationship, RelationshipType


def make_superuser(name='admin'):
    return get_user_model().objects.create_user(username=name, is_superuser=True)


def make_devices(*names):
    """Devices with the given names at one test site."""
    site = Site.objects.create(name='Test site', slug='test-site')
    maker = Manufacturer.objects.create(name='Maker', slug='maker')
    dtype = DeviceType.objects.create(manufacturer=maker, model='Box', slug='box')
    role = DeviceRole.objects.create(name='Server', slug='server')
    return [Device.objects.create(name=n, site=site, device_type=dtype, role=role) for n in names]


def needs(source, target, slug='depends-on'):
    """A relationship "source needs target" of a default type."""
    rel = Relationship(type=RelationshipType.objects.get(slug=slug), source=source, target=target)
    rel.full_clean()
    rel.save()
    return rel
