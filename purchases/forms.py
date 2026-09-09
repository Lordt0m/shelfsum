from django import forms
from django.core.exceptions import ValidationError
from django.forms import BaseInlineFormSet, inlineformset_factory
from decimal import Decimal

from catalogue.models import Product
from purchases.models import Purchase, PurchaseLine


class PurchaseForm(forms.ModelForm):
    class Meta:
        model = Purchase
        fields = ("purchase_date", "supplier_name", "reference", "notes")
        widgets = {
            "purchase_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }


class PurchaseLineForm(forms.ModelForm):
    quantity = forms.IntegerField(
        min_value=1,
        error_messages={"min_value": "Quantity must be a positive whole number."},
    )
    unit_cost = forms.DecimalField(min_value=0, max_digits=12, decimal_places=2)

    class Meta:
        model = PurchaseLine
        fields = ("product", "quantity", "unit_cost")

    def __init__(self, *args, business, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["product"].queryset = Product.objects.available_for_stock_activity(
            business=business
        )

    def clean(self):
        cleaned_data = super().clean()
        quantity = cleaned_data.get("quantity")
        unit_cost = cleaned_data.get("unit_cost")
        self.line_total = (
            quantity * unit_cost
            if quantity is not None and unit_cost is not None
            else Decimal("0")
        )
        return cleaned_data


class BasePurchaseLineFormSet(BaseInlineFormSet):
    def validate_unique(self):
        """Use the Purchase-specific duplicate message from ``clean`` below."""
        return

    def clean(self):
        super().clean()
        if any(self.errors):
            return

        product_ids = []
        for form in self.forms:
            if not form.cleaned_data or form.cleaned_data.get("DELETE"):
                continue
            product = form.cleaned_data.get("product")
            if product is not None:
                product_ids.append(product.pk)

        if len(product_ids) != len(set(product_ids)):
            raise ValidationError("A Product can appear only once on a Purchase.")

    @property
    def total(self):
        if not self.is_bound:
            return sum(
                (line.line_total for line in self.instance.lines.all()), Decimal("0")
            )
        return sum(
            (getattr(form, "line_total", Decimal("0")) for form in self.forms),
            Decimal("0"),
        )


PurchaseLineFormSet = inlineformset_factory(
    Purchase,
    PurchaseLine,
    form=PurchaseLineForm,
    formset=BasePurchaseLineFormSet,
    extra=3,
    can_delete=True,
)
