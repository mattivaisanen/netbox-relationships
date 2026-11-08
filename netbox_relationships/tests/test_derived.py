"""Links worked out from NetBox's own data stay current through signals."""
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from virtualization.models import Cluster, ClusterType, VirtualMachine

from ..models import EdgeIndex


def derived_targets(obj):
    """(content type id, pk) of everything `obj` needs through derived links."""
    rows = EdgeIndex.objects.filter(
        source_type=ContentType.objects.get_for_model(obj), source_id=obj.pk,
    ).exclude(origin='manual')
    return {(row.target_type_id, row.target_id) for row in rows}


class DerivedLinkTests(TestCase):
    def test_vm_follows_its_cluster(self):
        ctype = ClusterType.objects.create(name='Hypervisor', slug='hypervisor')
        first = Cluster.objects.create(name='first', type=ctype)
        second = Cluster.objects.create(name='second', type=ctype)
        cluster_ct = ContentType.objects.get_for_model(Cluster).pk

        vm = VirtualMachine.objects.create(name='vm', cluster=first)
        self.assertEqual(derived_targets(vm), {(cluster_ct, first.pk)})

        vm.cluster = second
        vm.save()
        self.assertEqual(derived_targets(vm), {(cluster_ct, second.pk)})
