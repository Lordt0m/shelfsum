from django.conf import settings
from django.db import models
from django.db.models import Q


class Business(models.Model):
    name = models.CharField(max_length=120)
    phone_number = models.CharField(max_length=30, blank=True)
    address = models.TextField(blank=True)
    currency = models.CharField(max_length=3, default="NGN", editable=False)
    timezone = models.CharField(max_length=40, default="Africa/Lagos", editable=False)
    is_demo = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Membership(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        STAFF = "staff", "Staff Member"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="membership",
    )
    business = models.ForeignKey(
        Business,
        on_delete=models.PROTECT,
        related_name="memberships",
    )
    role = models.CharField(max_length=10, choices=Role.choices)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["business"],
                condition=Q(role="owner"),
                name="one_owner_per_business",
            )
        ]

    def __str__(self):
        return f"{self.user} - {self.get_role_display()} at {self.business}"
