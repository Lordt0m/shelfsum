from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from auditing.models import AuditEvent
from auditing.services import record_audit_event
from businesses.models import Business, Membership
from catalogue.models import Product


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class RecordAuditEventServiceTests(TestCase):
    def test_ordinary_business_membership_can_record_an_audit_event(self):
        owner = get_user_model().objects.create_user(
            email="owner@example.com", password="password"
        )
        business = Business.objects.create(name="Ordinary Shop")
        Membership.objects.create(
            user=owner, business=business, role=Membership.Role.OWNER
        )
        product = Product.objects.create(
            business=business,
            name="Beans",
            sku="BEANS-001",
            selling_price="100.00",
            unit_cost="70.00",
        )

        event = record_audit_event(
            business=business,
            actor=owner,
            action="product.created",
            affected_object=product,
            summary="Created Beans.",
        )

        self.assertEqual(
            AuditEvent.objects.get(pk=event.pk).object_type,
            "catalogue.Product",
        )
        self.assertEqual(event.object_identifier, str(product.pk))
        self.assertEqual(event.summary, "Created Beans.")
