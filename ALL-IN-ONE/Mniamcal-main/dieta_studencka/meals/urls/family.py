from rest_framework.routers import DefaultRouter
from ..api_views.family import FamilyCreateViewSet, FamilyInviteByEmailViewSet

router = DefaultRouter()
router.register('families', FamilyCreateViewSet, basename='family-create')
router.register('family-invitations', FamilyInviteByEmailViewSet, basename='family-invite-by-email')

urlpatterns = router.urls
