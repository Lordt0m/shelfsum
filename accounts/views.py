from django.contrib.auth import login
from django.shortcuts import redirect, render

from accounts.forms import RegistrationForm


def register(request):
    if request.user.is_authenticated:
        return redirect("business_home")

    form = RegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        return redirect("business_create")

    return render(
        request,
        "accounts/form_page.html",
        {
            "form": form,
            "page_title": "Create your account",
            "intro": "Use your email address to create a private ShelfSum account.",
            "submit_label": "Create account",
            "alternate_text": "Already registered?",
            "alternate_url": "sign_in",
            "alternate_label": "Sign in",
        },
    )
