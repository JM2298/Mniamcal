from django.urls import path

from ..api_views import StoreCurrentPriceUpdateViewSet


urlpatterns = [
	path(
		'settings/stores/current-prices/update/',
		StoreCurrentPriceUpdateViewSet.as_view({'post': 'create', 'put': 'update'}),
		name='settings-store-current-prices-update',
	),
]
