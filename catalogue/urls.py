from django.urls import path

from catalogue import views


urlpatterns = [
    path("", views.product_list, name="product_list"),
    path("new/", views.product_create, name="product_create"),
    path("<int:product_id>/", views.product_detail, name="product_detail"),
]
