from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0011_reminderlog'),
    ]

    operations = [
        migrations.AlterField(
            model_name='reminderlog',
            name='period',
            field=models.CharField(max_length=10),
        ),
        migrations.AlterField(
            model_name='reminderlog',
            name='reminder_type',
            field=models.CharField(
                choices=[
                    ('general', "Barcha o'quvchilar uchun umumiy to'lov eslatmasi (har 5 kunda)"),
                    ('individual', "15-sanadan keyingi har bir qarzdorga alohida ogohlantirish"),
                ],
                max_length=20,
            ),
        ),
    ]
