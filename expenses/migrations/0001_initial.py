from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings

class Migration(migrations.Migration):
    initial = True
    dependencies = [("accounts", "0001_initial"), ("businesses", "0001_initial")]
    operations = [migrations.CreateModel(name="Expense", fields=[
        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
        ("date", models.DateField()), ("category", models.CharField(choices=[("rent", "Rent"), ("utilities", "Utilities"), ("transport", "Transport"), ("maintenance", "Maintenance"), ("supplies", "Supplies"), ("other", "Other")], max_length=20)),
        ("description", models.CharField(max_length=240)), ("amount", models.DecimalField(decimal_places=2, max_digits=12)), ("notes", models.TextField(blank=True)),
        ("status", models.CharField(choices=[("recorded", "Recorded"), ("voided", "Voided")], default="recorded", max_length=10)), ("created_at", models.DateTimeField(auto_now_add=True)),
        ("actor", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="expenses_recorded", to=settings.AUTH_USER_MODEL)),
        ("business", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="expenses", to="businesses.business")),
        ("correction_of", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="replacement", to="expenses.expense")),
    ], options={"ordering": ("-date", "-pk"), "constraints": [models.CheckConstraint(condition=models.Q(amount__gt=0), name="expense_positive_amount")]})]
