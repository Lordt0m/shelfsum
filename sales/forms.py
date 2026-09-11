from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.forms import BaseInlineFormSet, inlineformset_factory

from catalogue.models import Product
from sales.models import Sale, SaleLine


class SaleForm(forms.ModelForm):
    class Meta:
        model = Sale
        fields = ("sale_date", "customer_name", "reference", "notes")
        widgets = {"sale_date": forms.DateInput(attrs={"type": "date"}), "notes": forms.Textarea(attrs={"rows": 3})}


class SaleLineForm(forms.ModelForm):
    quantity = forms.IntegerField(min_value=1, error_messages={"min_value": "Quantity must be a positive whole number."})
    unit_price = forms.DecimalField(min_value=0, max_digits=12, decimal_places=2)

    class Meta:
        model = SaleLine
        fields = ("product", "quantity", "unit_price")

    def __init__(self, *args, business, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["product"].queryset = Product.objects.available_for_stock_activity(business=business)

    def clean(self):
        cleaned_data = super().clean()
        quantity, unit_price = cleaned_data.get("quantity"), cleaned_data.get("unit_price")
        self.line_total = quantity * unit_price if quantity is not None and unit_price is not None else Decimal("0")
        return cleaned_data


class BaseSaleLineFormSet(BaseInlineFormSet):
    def validate_unique(self):
        return

    def clean(self):
        super().clean()
        if any(self.errors):
            return
        product_ids = [form.cleaned_data.get("product").pk for form in self.forms if form.cleaned_data and not form.cleaned_data.get("DELETE") and form.cleaned_data.get("product") is not None]
        if len(product_ids) != len(set(product_ids)):
            raise ValidationError("A Product can appear only once on a Sale.")
        for form in self.forms:
            if not form.cleaned_data or form.cleaned_data.get("DELETE"):
                continue
            product = form.cleaned_data.get("product")
            quantity = form.cleaned_data.get("quantity")
            if product is not None and quantity is not None and quantity > product.stock_on_hand:
                raise ValidationError(
                    f"Quantity for {product.name} exceeds available Stock on Hand ({product.stock_on_hand})."
                )

    @property
    def total(self):
        if not self.is_bound:
            return sum((line.line_total for line in self.instance.lines.all()), Decimal("0"))
        return sum((getattr(form, "line_total", Decimal("0")) for form in self.forms), Decimal("0"))


SaleLineFormSet = inlineformset_factory(Sale, SaleLine, form=SaleLineForm, formset=BaseSaleLineFormSet, extra=3, can_delete=True)
