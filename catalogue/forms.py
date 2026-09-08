from django import forms

from catalogue.models import Product
from catalogue.services import ProductCreation


NONNEGATIVE_ERROR = "This value cannot be negative."


class ProductCreationForm(forms.ModelForm):
    selling_price = forms.DecimalField(
        min_value=0, max_digits=12, decimal_places=2,
        error_messages={"min_value": NONNEGATIVE_ERROR},
    )
    unit_cost = forms.DecimalField(
        min_value=0, max_digits=12, decimal_places=2,
        error_messages={"min_value": NONNEGATIVE_ERROR},
        label="Unit-cost estimate",
    )
    opening_quantity = forms.IntegerField(
        min_value=0,
        error_messages={"min_value": NONNEGATIVE_ERROR},
        help_text="Use zero when no stock is currently available.",
    )
    low_stock_threshold = forms.IntegerField(
        min_value=0,
        error_messages={"min_value": NONNEGATIVE_ERROR},
    )

    class Meta:
        model = Product
        fields = (
            "name",
            "sku",
            "description",
            "selling_price",
            "unit_cost",
            "opening_quantity",
            "low_stock_threshold",
        )
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, business, **kwargs):
        super().__init__(*args, **kwargs)
        self.business = business

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if Product.objects.filter(business=self.business, name__iexact=name).exists():
            raise forms.ValidationError("A Product with this name already exists.")
        return name

    def clean_sku(self):
        sku = self.cleaned_data["sku"].strip().upper()
        if sku and Product.objects.filter(business=self.business, sku__iexact=sku).exists():
            raise forms.ValidationError("A Product with this SKU already exists.")
        return sku

    def to_product_creation(self):
        return ProductCreation(
            name=self.cleaned_data["name"],
            sku=self.cleaned_data["sku"],
            description=self.cleaned_data["description"],
            selling_price=self.cleaned_data["selling_price"],
            unit_cost=self.cleaned_data["unit_cost"],
            opening_quantity=self.cleaned_data["opening_quantity"],
            low_stock_threshold=self.cleaned_data["low_stock_threshold"],
        )
