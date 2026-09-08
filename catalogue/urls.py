from django.urls import path

from catalogue import views


urlpatterns = [
    path("", views.product_list, name="product_list"),
    path("new/", views.product_create, name="product_create"),
    path("<int:product_id>/", views.product_detail, name="product_detail"),
    path("<int:product_id>/edit/", views.product_edit, name="product_edit"),
    path("<int:product_id>/deactivate/", views.product_deactivate, name="product_deactivate"),
]
