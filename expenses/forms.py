from django import forms
from .models import Expense

class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ["date", "category", "description", "amount", "notes"]
        widgets = {"date": forms.DateInput(attrs={"type": "date"}), "amount": forms.NumberInput(attrs={"step": "0.01", "min": "0.01"})}
    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        if amount <= 0: raise forms.ValidationError("Amount must be greater than zero.")
        return amount
