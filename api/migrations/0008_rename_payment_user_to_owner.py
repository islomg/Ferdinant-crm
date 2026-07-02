from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0007_backfill_payment_owner'),
    ]

    operations = [
        migrations.RenameField(
            model_name='payment',
            old_name='user',
            new_name='owner',
        ),
    ]
