from django.urls import path
from rest_framework.routers import DefaultRouter

from ..api_views import AuthMeViewSet, AuthTokenRefreshView, FcmDeviceRegisterViewSet, FcmSendNotificationViewSet, GoogleOAuthLoginViewSet, LoginViewSet, RegisterViewSet

router = DefaultRouter()
router.register('auth/login', LoginViewSet, basename='auth-login')
router.register('auth/login/firebase', GoogleOAuthLoginViewSet, basename='auth-login-firebase')
router.register('auth/login/google', GoogleOAuthLoginViewSet, basename='auth-login-google')
router.register('auth/register', RegisterViewSet, basename='auth-register')
router.register('auth/me', AuthMeViewSet, basename='auth-me')
router.register('fcm/devices', FcmDeviceRegisterViewSet, basename='fcm-device-register')
router.register('fcm/send', FcmSendNotificationViewSet, basename='fcm-send')

urlpatterns = router.urls
urlpatterns += [
	path('auth/token/refresh/', AuthTokenRefreshView.as_view(), name='token-refresh'),
]
