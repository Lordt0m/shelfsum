from django import forms

from catalogue.models import Product
from .models import StockAdjustment


class StockAdjustmentForm(forms.ModelForm):
    class Meta:
        model = StockAdjustment
        fields = ["product", "quantity_change", "reason", "notes"]
        widgets = {"quantity_change": forms.NumberInput(attrs={"step": "1"})}

    def __init__(self, *args, business, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["product"].queryset = Product.objects.available_for_stock_activity(business=business)
        self.fields["reason"].choices = [
            (value, label) for value, label in StockAdjustment.Reason.choices
            if value != StockAdjustment.Reason.OPENING
        ]

    def clean_quantity_change(self):
        value = self.cleaned_data["quantity_change"]
        if isinstance(value, bool) or not isinstance(value, int) or value == 0:
            raise forms.ValidationError("Enter a nonzero whole-number change.")
        return value
