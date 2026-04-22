from rest_framework.routers import DefaultRouter

from ..api_views.kalendar import FamilyPlannedMealCreateViewSet


router = DefaultRouter()
router.register('calendar/family-planned-meals', FamilyPlannedMealCreateViewSet, basename='family-planned-meals')

urlpatterns = router.urls
