"""
URL configuration for dieta_studencka project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView




urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', TemplateView.as_view(template_name='login.html'), name='firebase-login-page'),
    path(
        'account-deletion-request/',
        TemplateView.as_view(template_name='account_deletion_request.html'),
        name='account-deletion-request-page',
    ),
    path(
        'usuniecie-konta/',
        TemplateView.as_view(template_name='account_deletion_request.html'),
        name='usuniecie-konta-page',
    ),
    path(
        'privacy-policy/',
        TemplateView.as_view(template_name='privacy_policy.html'),
        name='privacy-policy-page',
    ),
    path(
        'polityka-prywatnosci/',
        TemplateView.as_view(template_name='privacy_policy.html'),
        name='polityka-prywatnosci-page',
    ),
    path('api/', include('meals.urls')),
    path('api/schema/', SpectacularAPIView.as_view(), name='api-schema'),
    path('docs/swagger/', SpectacularSwaggerView.as_view(url_name='api-schema'), name='swagger-ui'),
    path('docs/redoc/', SpectacularRedocView.as_view(url_name='api-schema'), name='redoc'),
]

