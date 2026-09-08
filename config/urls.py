from django.contrib import admin
from django.urls import path

from core import views

urlpatterns = [
    path("", views.landing, name="landing"),
    path("health/", views.health, name="health"),
    path("admin/", admin.site.urls),
]
