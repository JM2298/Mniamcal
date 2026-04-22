from rest_framework.routers import DefaultRouter

from ..api_views.shoping_list import (
	FamilyShoppingListFromCalendarCreateViewSet,
	FamilyShoppingListMarkBoughtViewSet,
	FamilyShoppingListReadViewSet,
)


router = DefaultRouter()
router.register('shopping-lists/from-calendar', FamilyShoppingListFromCalendarCreateViewSet, basename='family-shopping-list-from-calendar')
router.register('shopping-lists/products/mark-bought', FamilyShoppingListMarkBoughtViewSet, basename='family-shopping-list-mark-bought')
router.register('shopping-lists', FamilyShoppingListReadViewSet, basename='family-shopping-list-read')

urlpatterns = router.urls
