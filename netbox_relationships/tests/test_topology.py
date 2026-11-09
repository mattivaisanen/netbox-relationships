"""Network cables become uplinks between tiers, through patch panels and virtual chassis."""
import copy

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase, override_settings

from dcim.models import (
    Cable, Device, DeviceRole, DeviceType, FrontPort, Interface, Manufacturer, PortMapping, RearPort, Site,
    VirtualChassis,
)

from ..edges import rebuild
from ..impact import analyse
from ..models import EdgeIndex, NetworkTier
from .utils import make_superuser


def tiered():
    """PLUGINS_CONFIG with three tiers set, the rest as configured."""
    config = copy.deepcopy(settings.PLUGINS_CONFIG)
    config['netbox_relationships']['network_tiers'] = [['core'], ['distribution'], ['access']]
    return config


@override_settings(PLUGINS_CONFIG=tiered())
class UplinkTests(TestCase):
    """
    An access switch cabled through a patch panel to one member of a
    two-switch distribution chassis, and directly to the other member.
    """

    def setUp(self):
        site = Site.objects.create(name='Site one', slug='site-one')
        maker = Manufacturer.objects.create(name='Maker', slug='maker')
        switch = DeviceType.objects.create(manufacturer=maker, model='Switch', slug='switch')
        panel_type = DeviceType.objects.create(manufacturer=maker, model='Panel', slug='panel')
        role = {slug: DeviceRole.objects.create(name=slug, slug=slug) for slug in ('distribution', 'access', 'patch')}
        self.pair = VirtualChassis.objects.create(name='dist-pair')
        self.d1, self.d2 = (
            Device.objects.create(name=f'dist-{n}', site=site, device_type=switch, role=role['distribution'],
                                  virtual_chassis=self.pair, vc_position=n)
            for n in (1, 2)
        )
        self.access = Device.objects.create(name='acc', site=site, device_type=switch, role=role['access'])
        panel = Device.objects.create(name='panel', site=site, device_type=panel_type, role=role['patch'])
        rear = RearPort.objects.create(device=panel, name='R1', type='lc', positions=1)
        front = FrontPort.objects.create(device=panel, name='F1', type='lc')
        PortMapping.objects.create(device=panel, front_port=front, rear_port=rear, front_port_position=1,
                                   rear_port_position=1)

        def port(device, name):
            return Interface.objects.create(device=device, name=name, type='10gbase-x-sfpp')

        Cable(a_terminations=[port(self.access, 'up1')], b_terminations=[front]).save()
        Cable(a_terminations=[rear], b_terminations=[port(self.d1, 'down1')]).save()
        Cable(a_terminations=[port(self.access, 'up2')], b_terminations=[port(self.d2, 'down2')]).save()
        rebuild()

    def test_access_switch_uplinks_to_the_chassis_through_the_panel(self):
        edge = EdgeIndex.objects.get(origin='cables')
        self.assertEqual(
            (edge.source_type, edge.source_id, edge.target_type, edge.target_id, edge.link_count, edge.group),
            (ContentType.objects.get_for_model(Device), self.access.pk,
             ContentType.objects.get_for_model(VirtualChassis), self.pair.pk, 2, 'uplinks'),
        )

    def test_losing_one_chassis_member_leaves_the_access_switch_at_risk(self):
        device_ct = ContentType.objects.get_for_model(Device).pk
        user = make_superuser()

        def states(*devices):
            result = analyse(user, [(device_ct, device.pk) for device in devices])
            return {entry['label']: entry['state'] for entry in result['affected']}

        self.assertEqual(states(self.d1), {'dist-pair': 'at_risk', 'acc': 'at_risk'})
        self.assertEqual(states(self.d1, self.d2), {'dist-pair': 'down', 'acc': 'down'})

    def test_tiers_made_in_the_ui_win_over_the_setting(self):
        # Turned upside down: access on top, so the chassis now needs the access switch.
        with self.captureOnCommitCallbacks(execute=True):
            for level, slug in ((1, 'access'), (2, 'distribution')):
                tier = NetworkTier.objects.create(name=slug, slug=slug, level=level)
                tier.roles.set([DeviceRole.objects.get(slug=slug)])
        edge = EdgeIndex.objects.get(origin='cables')
        self.assertEqual((edge.source_id, edge.target_id), (self.pair.pk, self.access.pk))
