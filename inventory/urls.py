from django.urls import path
from . import views

urlpatterns = [
    path("", views.adjustment_list, name="adjustment_list"),
    path("", views.adjustment_list, name="stock_adjustment_list"),
    path("new/", views.adjustment_create, name="adjustment_create"),
    path("new/", views.adjustment_create, name="stock_adjustment_create"),
    path("<int:adjustment_id>/", views.adjustment_detail, name="adjustment_detail"),
    path("<int:adjustment_id>/", views.adjustment_detail, name="stock_adjustment_detail"),
]
