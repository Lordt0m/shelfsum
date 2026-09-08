from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET


def landing(request):
    return render(request, "core/landing.html")


@require_GET
def health(request):
    response = JsonResponse({"status": "ok"})
    response.headers["Cache-Control"] = "no-store"
    return response
