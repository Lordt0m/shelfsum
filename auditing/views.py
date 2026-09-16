from django.shortcuts import render

from auditing.browser import build_audit_event_browser
from businesses.access import membership_required


@membership_required
def audit_event_list(request):
    return render(
        request,
        "auditing/audit_event_list.html",
        {"browser": build_audit_event_browser(business=request.business, query_params=request.GET)},
    )
