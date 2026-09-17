from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from core.demo import (
    DEMO_OWNER_EMAIL,
    DEMO_OWNER_PASSWORD,
    DEMO_STAFF_EMAIL,
    DEMO_STAFF_PASSWORD,
)


def landing(request):
    return render(
        request,
        "core/landing.html",
        {
            "demo_owner_email": DEMO_OWNER_EMAIL,
            "demo_owner_password": DEMO_OWNER_PASSWORD,
            "demo_staff_email": DEMO_STAFF_EMAIL,
            "demo_staff_password": DEMO_STAFF_PASSWORD,
        },
    )


@require_GET
def health(request):
    response = JsonResponse({"status": "ok"})
    response.headers["Cache-Control"] = "no-store"
    return response
