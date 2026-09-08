from django.db import migrations, models
import django.db.models.deletion


def remove_untraceable_movements(apps, schema_editor):
    stock_movement = apps.get_model("inventory", "StockMovement")
    stock_movement.objects.filter(stock_adjustment__isnull=True).delete()


class Migration(migrations.Migration):
    dependencies = [("inventory", "0001_initial")]

    operations = [
        migrations.RunPython(remove_untraceable_movements, migrations.RunPython.noop),
        migrations.RemoveField(model_name="stockmovement", name="reversal_of"),
        migrations.AlterField(
            model_name="stockmovement",
            name="kind",
            field=models.CharField(
                choices=[("adjustment", "Stock Adjustment")], max_length=20
            ),
        ),
        migrations.AlterField(
            model_name="stockmovement",
            name="stock_adjustment",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="movement",
                to="inventory.stockadjustment",
            ),
        ),
    ]
