from rest_framework.routers import DefaultRouter

from ..api_views.warehouse import FamilyWarehouseReadViewSet


router = DefaultRouter()
router.register('warehouse', FamilyWarehouseReadViewSet, basename='family-warehouse-read')

urlpatterns = router.urls
