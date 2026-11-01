"""
URL configuration for project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
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
from oauth2_provider import views as oauth_views
from oauth2_provider.urls import metadata_urlpatterns

from foodlog.mcp_auth import OwnerAuthorizationView

oauth_urls = [
    path("authorize/", OwnerAuthorizationView.as_view(), name="authorize"),
    path("token/", oauth_views.TokenView.as_view(), name="token"),
    path("revoke_token/", oauth_views.RevokeTokenView.as_view(), name="revoke-token"),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path(
        "oauth/", include((oauth_urls, "oauth2_provider"), namespace="oauth2_provider")
    ),
    *metadata_urlpatterns,
]
