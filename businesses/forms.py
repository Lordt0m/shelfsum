from django import forms

from businesses.models import Business


class BusinessForm(forms.ModelForm):
    class Meta:
        model = Business
        fields = ("name", "phone_number", "address")
        labels = {"phone_number": "Phone number"}
        widgets = {
            "name": forms.TextInput(attrs={"autocomplete": "organization"}),
            "phone_number": forms.TextInput(attrs={"autocomplete": "tel"}),
            "address": forms.Textarea(attrs={"rows": 4, "autocomplete": "street-address"}),
        }


class StaffMemberForm(forms.Form):
    email = forms.EmailField(
        label="Registered user email",
        widget=forms.EmailInput(attrs={"autocomplete": "email"}),
    )

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()
