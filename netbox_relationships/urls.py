from django.urls import include, path

from utilities.urls import get_model_urls

from . import assets, views

urlpatterns = [
    path('impact/', views.ImpactView.as_view(), name='impact'),
    path('service-map/', views.ServiceMapView.as_view(), name='servicemap'),
    path('assets/<str:name>', assets.asset, name='asset'),

    path('relationships/', include(get_model_urls('netbox_relationships', 'relationship', detail=False))),
    path('relationships/<int:pk>/', include(get_model_urls('netbox_relationships', 'relationship'))),
    path('types/', include(get_model_urls('netbox_relationships', 'relationshiptype', detail=False))),
    path('types/<int:pk>/', include(get_model_urls('netbox_relationships', 'relationshiptype'))),
    path('services/', include(get_model_urls('netbox_relationships', 'logicalservice', detail=False))),
    path('services/<int:pk>/', include(get_model_urls('netbox_relationships', 'logicalservice'))),
]
