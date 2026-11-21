from django.urls import include, path

from utilities.urls import get_model_urls

from . import assets, views

urlpatterns = [
    path('impact/', views.ImpactView.as_view(), name='impact'),
    path('service-map/', views.ServiceMapView.as_view(), name='servicemap'),
    path('assets/<str:name>', assets.asset, name='asset'),
    path('links/', views.LinkListView.as_view(), name='link_list'),
    path('links/rebuild/', views.RebuildIndexView.as_view(), name='rebuild_index'),
    path('relationships/add-many/', views.RelationshipAddManyView.as_view(), name='relationship_add_many'),
    path('types/add-common/', views.AddCommonTypesView.as_view(), name='relationshiptype_add_common'),

    path('relationships/', include(get_model_urls('netbox_relationships', 'relationship', detail=False))),
    path('relationships/<int:pk>/', include(get_model_urls('netbox_relationships', 'relationship'))),
    path('types/', include(get_model_urls('netbox_relationships', 'relationshiptype', detail=False))),
    path('types/<int:pk>/', include(get_model_urls('netbox_relationships', 'relationshiptype'))),
    path('services/', include(get_model_urls('netbox_relationships', 'logicalservice', detail=False))),
    path('services/<int:pk>/', include(get_model_urls('netbox_relationships', 'logicalservice'))),
    path('tiers/', include(get_model_urls('netbox_relationships', 'networktier', detail=False))),
    path('tiers/<int:pk>/', include(get_model_urls('netbox_relationships', 'networktier'))),
]
