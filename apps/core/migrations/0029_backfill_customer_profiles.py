from django.db import migrations
from django.conf import settings


def backfill_customer_profiles(apps, schema_editor):
    """Create Customer profiles for users who don't have one and assign sequential IDs."""
    Customer = apps.get_model('core', 'Customer')
    User = apps.get_model(settings.AUTH_USER_MODEL.split('.')[0], settings.AUTH_USER_MODEL.split('.')[1])

    # Find the current max customer_id
    from django.db.models import IntegerField
    from django.db.models.functions import Cast
    last = (
        Customer.objects
        .annotate(id_int=Cast('customer_id', IntegerField()))
        .order_by('-id_int')
        .values_list('id_int', flat=True)
        .first()
    )
    next_id = (last or 1110) + 1

    # Create Customer for every user that doesn't have one
    users_without = User.objects.exclude(
        id__in=Customer.objects.values_list('user_id', flat=True)
    ).order_by('date_joined')

    for user in users_without:
        Customer.objects.create(user=user, customer_id=str(next_id))
        next_id += 1


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0028_convert_customer_ids'),
    ]

    operations = [
        migrations.RunPython(backfill_customer_profiles, migrations.RunPython.noop),
    ]
