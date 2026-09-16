from django.urls import path

from auditing import views


urlpatterns = [
    path("", views.audit_event_list, name="audit_event_list"),
]
