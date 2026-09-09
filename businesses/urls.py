from django.urls import path

from businesses import views


urlpatterns = [
    path("create/", views.create_business, name="business_create"),
    path("", views.business_home, name="business_home"),
    path("settings/", views.business_settings, name="business_settings"),
    path("staff/", views.staff_member_list, name="staff_member_list"),
    path("staff/add/", views.staff_member_add, name="staff_member_add"),
    path(
        "staff/<int:membership_id>/deactivate/",
        views.staff_member_deactivate,
        name="staff_member_deactivate",
    ),
]
