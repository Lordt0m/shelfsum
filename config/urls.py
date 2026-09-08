from django.contrib import admin
from django.urls import include, path

from core import views

urlpatterns = [
    path("", views.landing, name="landing"),
    path("health/", views.health, name="health"),
    path("auth/", include("accounts.urls")),
    path("business/", include("businesses.urls")),
    path("products/", include("catalogue.urls")),
    path("admin/", admin.site.urls),
]
