from django.urls import path

from businesses import views


urlpatterns = [
    path("create/", views.create_business, name="business_create"),
    path("", views.business_home, name="business_home"),
    path("settings/", views.business_settings, name="business_settings"),
]
