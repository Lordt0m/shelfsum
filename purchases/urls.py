from django.urls import path
from purchases import views
urlpatterns = [path("", views.purchase_list, name="purchase_list"), path("new/", views.purchase_create, name="purchase_create"), path("<int:purchase_id>/", views.purchase_detail, name="purchase_detail"), path("<int:purchase_id>/edit/", views.purchase_edit, name="purchase_edit")]
