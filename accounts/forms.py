from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.exceptions import ValidationError

from accounts.models import User


class RegistrationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("email",)

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("This email address is already registered.")
        return email


class EmailAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Email address"
        self.fields["username"].widget.attrs.update(
            {"autocomplete": "email", "autofocus": True}
        )

    def clean_username(self):
        return self.cleaned_data["username"].strip().lower()
