from django.db import migrations


def convert_customer_ids(apps, schema_editor):
    """Convert existing DF-XXXXXX customer IDs to sequential 4-digit IDs starting from 1111."""
    Customer = apps.get_model('core', 'Customer')
    customers = Customer.objects.all().order_by('created_at')
    next_id = 1111
    for customer in customers:
        customer.customer_id = str(next_id)
        customer.save(update_fields=['customer_id'])
        next_id += 1


def reverse_migration(apps, schema_editor):
    """No reliable reverse since original IDs are lost."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0027_alter_combo_image_alter_combo_modal_image_and_more'),
    ]

    operations = [
        migrations.RunPython(convert_customer_ids, reverse_migration),
    ]
