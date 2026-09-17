from django.contrib.auth import views as auth_views
from django.urls import path
from django.urls import reverse_lazy

from accounts import views
from accounts.forms import EmailAuthenticationForm
from businesses.access import demo_business_read_only


urlpatterns = [
    path("register/", views.register, name="register"),
    path(
        "sign-in/",
        auth_views.LoginView.as_view(
            template_name="accounts/form_page.html",
            authentication_form=EmailAuthenticationForm,
            extra_context={
                "page_title": "Sign in",
                "intro": "Continue to your Business using your email address.",
                "submit_label": "Sign in",
                "alternate_text": "New to ShelfSum?",
                "alternate_url": "register",
                "alternate_label": "Create an account",
            },
        ),
        name="sign_in",
    ),
    path(
        "sign-out/",
        auth_views.LogoutView.as_view(next_page="landing"),
        name="sign_out",
    ),
    path(
        "password/change/",
        demo_business_read_only(auth_views.PasswordChangeView.as_view(
            template_name="accounts/form_page.html",
            success_url=reverse_lazy("password_change_done"),
            extra_context={
                "page_title": "Change password",
                "intro": "Confirm your current password before choosing a replacement.",
                "submit_label": "Change password",
            },
        )),
        name="password_change",
    ),
    path(
        "password/change/done/",
        auth_views.PasswordChangeDoneView.as_view(
            template_name="accounts/password_change_done.html"
        ),
        name="password_change_done",
    ),
]
