from django.urls import path
from . import views

urlpatterns = [
    path("", views.expense_list, name="expense_list"),
    path("new/", views.expense_create, name="expense_create"),
    path("<int:expense_id>/", views.expense_detail, name="expense_detail"),
    path("<int:expense_id>/void/", views.expense_void, name="expense_void"),
    path("<int:expense_id>/correct/", views.expense_correct, name="expense_correct"),
]
