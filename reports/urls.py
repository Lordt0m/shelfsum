from django.urls import path

from reports import views


urlpatterns = [
    path("sales/", views.sales_report, name="reports_sales"),
    path("sales.csv", views.sales_report_csv, name="reports_sales_csv"),
]
