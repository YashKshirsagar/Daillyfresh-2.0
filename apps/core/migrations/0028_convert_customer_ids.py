from django.db import migrations
from django.conf import settings


def convert_customer_ids(apps, schema_editor):
    """Create missing Customer profiles and convert all IDs to sequential 4-digit format."""
    Customer = apps.get_model('core', 'Customer')
    User = apps.get_model(settings.AUTH_USER_MODEL.split('.')[0], settings.AUTH_USER_MODEL.split('.')[1])

    # Create Customer profiles for users who don't have one
    for user in User.objects.all():
        Customer.objects.get_or_create(user=user)

    # Now convert all customer IDs to sequential 4-digit format
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
