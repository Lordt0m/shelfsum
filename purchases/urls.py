from django.urls import path
from purchases import views
urlpatterns = [path("", views.purchase_list, name="purchase_list"), path("new/", views.purchase_create, name="purchase_create"), path("<int:purchase_id>/", views.purchase_detail, name="purchase_detail"), path("<int:purchase_id>/edit/", views.purchase_edit, name="purchase_edit"), path("<int:purchase_id>/void/", views.purchase_void, name="purchase_void"), path("<int:purchase_id>/void/confirm/", views.purchase_void, name="purchase_void_confirm")]
