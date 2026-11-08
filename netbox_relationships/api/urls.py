from django.urls import path

from netbox.api.routers import NetBoxRouter

from . import views

router = NetBoxRouter()
router.register('relationship-types', views.RelationshipTypeViewSet)
router.register('relationships', views.RelationshipViewSet)
router.register('logical-services', views.LogicalServiceViewSet)

urlpatterns = [
    path('graph/', views.GraphView.as_view(), name='graph'),
    path('impact/', views.ImpactView.as_view(), name='impact'),
] + router.urls
