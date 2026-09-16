from django.urls import path

from reports import views


urlpatterns = [
    path("", views.reports_index, name="reports_index"),
    path("sales/", views.sales_report, name="reports_sales"),
    path("sales.csv", views.sales_report_csv, name="reports_sales_csv"),
    path("purchases/", views.purchase_report, name="reports_purchases"),
    path("purchases.csv", views.purchase_report_csv, name="reports_purchases_csv"),
    path("expenses/", views.expense_report, name="reports_expenses"),
    path("expenses.csv", views.expense_report_csv, name="reports_expenses_csv"),
]
