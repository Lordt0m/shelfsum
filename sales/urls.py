from django.urls import path

from sales import views

urlpatterns = [
    path("", views.sale_list, name="sale_list"),
    path("new/", views.sale_create, name="sale_create"),
    path("<int:sale_id>/", views.sale_detail, name="sale_detail"),
    path("<int:sale_id>/edit/", views.sale_edit, name="sale_edit"),
]
