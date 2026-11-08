from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from netbox.api.authentication import IsAuthenticatedOrLoginNotRequired
from netbox.api.viewsets import NetBoxModelViewSet

from .. import filtersets, graph, impact
from ..models import LogicalService, Relationship, RelationshipType
from . import serializers

PERMISSION = 'netbox_relationships.view_relationship'


class RelationshipTypeViewSet(NetBoxModelViewSet):
    queryset = RelationshipType.objects.prefetch_related('source_types', 'target_types', 'tags')
    serializer_class = serializers.RelationshipTypeSerializer
    filterset_class = filtersets.RelationshipTypeFilterSet


class RelationshipViewSet(NetBoxModelViewSet):
    queryset = Relationship.objects.select_related('type', 'source_type', 'target_type').prefetch_related('tags')
    serializer_class = serializers.RelationshipSerializer
    filterset_class = filtersets.RelationshipFilterSet


class LogicalServiceViewSet(NetBoxModelViewSet):
    queryset = LogicalService.objects.select_related('parent', 'tenant').prefetch_related('tags')
    serializer_class = serializers.LogicalServiceSerializer
    filterset_class = filtersets.LogicalServiceFilterSet


def _objects(values):
    """(ct, pk) pairs from "dcim.device:42" or "<ct id>:42" strings."""
    found = []
    for value in values:
        parsed = graph.parse_key(value)
        if parsed is None:
            raise ValidationError({'object': f'Not an object reference: {value!r}. Use "dcim.device:42".'})
        found.append(parsed)
    if not found:
        raise ValidationError({'object': 'Give at least one object.'})
    return found


class _AnalysisView(APIView):
    permission_classes = (IsAuthenticatedOrLoginNotRequired,)

    def check_permissions(self, request):
        super().check_permissions(request)
        if not request.user.has_perm(PERMISSION):
            raise PermissionDenied('Viewing relationships is not permitted.')


class GraphView(_AnalysisView):
    """
    GET ?object=<ref>[&object=...]&direction=down|up|both&depth=N&derived=true|false&type=<id>...

    Nodes and edges around the objects. Objects the user may not view are
    hidden placeholders (or left out, by the `hidden_nodes` setting).
    """

    def get(self, request):
        direction = request.query_params.get('direction', graph.BOTH)
        if direction not in (graph.DOWN, graph.UP, graph.BOTH):
            raise ValidationError({'direction': 'Use down, up or both.'})
        filters = graph.Filters(
            derived=request.query_params.get('derived', 'true').lower() != 'false',
            statuses=request.query_params.getlist('status') or None,
            rtypes=[int(v) for v in request.query_params.getlist('type') if v.isdigit()] or None,
        )
        return Response(graph.build(
            request.user, _objects(request.query_params.getlist('object')),
            direction=direction, depth=request.query_params.get('depth'), filters=filters,
        ))


class ImpactView(_AnalysisView):
    """
    POST {"objects": ["dcim.device:42", ...], "include_planned": false}

    What goes down or is degraded when these objects fail, and why.
    """

    def post(self, request):
        objects = request.data.get('objects') or []
        if not isinstance(objects, list):
            raise ValidationError({'objects': 'A list of object references.'})
        include_planned = request.data.get('include_planned')
        result = impact.analyse(request.user, _objects(objects), include_planned=include_planned)
        return Response(impact.serializable(result))
