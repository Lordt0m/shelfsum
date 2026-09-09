from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower

from businesses.models import Business


class ProductQuerySet(models.QuerySet):
    def for_business(self, business):
        return self.filter(business=business)

    def available_for_stock_activity(self, *, business):
        return self.for_business(business).filter(is_active=True)


class Product(models.Model):
    business = models.ForeignKey(Business, on_delete=models.PROTECT, related_name="products")
    name = models.CharField(max_length=120)
    sku = models.CharField("SKU", max_length=60, blank=True)
    description = models.TextField(blank=True)
    selling_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    stock_on_hand = models.PositiveIntegerField(default=0, editable=False)
    low_stock_threshold = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ProductQuerySet.as_manager()

    class Meta:
        ordering = ("name", "pk")
        constraints = [
            models.UniqueConstraint(
                Lower("name"), "business", name="unique_product_name_per_business"
            ),
            models.UniqueConstraint(
                Lower("sku"),
                "business",
                condition=~Q(sku=""),
                name="unique_nonempty_sku_per_business",
            ),
            models.CheckConstraint(
                condition=Q(selling_price__gte=0), name="nonnegative_selling_price"
            ),
            models.CheckConstraint(condition=Q(unit_cost__gte=0), name="nonnegative_unit_cost"),
            models.CheckConstraint(
                condition=Q(stock_on_hand__gte=0), name="nonnegative_stock_on_hand"
            ),
            models.CheckConstraint(
                condition=Q(low_stock_threshold__gte=0), name="nonnegative_low_stock_threshold"
            ),
        ]

    @property
    def is_low_stock(self):
        return self.stock_on_hand <= self.low_stock_threshold

    def save(self, *args, **kwargs):
        self.name = self.name.strip()
        self.sku = self.sku.strip().upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name
