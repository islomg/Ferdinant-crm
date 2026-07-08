from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0012_reminderlog_general_period'),
    ]

    operations = [
        migrations.AddField(
            model_name='group',
            name='telegram_chat_id',
            field=models.CharField(blank=True, default='', max_length=64),
        ),
        migrations.AlterField(
            model_name='reminderlog',
            name='period',
            field=models.CharField(max_length=40),
        ),
        migrations.AlterField(
            model_name='reminderlog',
            name='reminder_type',
            field=models.CharField(
                choices=[
                    ('general', "Barcha o'quvchilar uchun umumiy to'lov eslatmasi (har 5 kunda)"),
                    ('individual', "15-sanadan keyingi har bir qarzdorga alohida ogohlantirish"),
                    ('group_lesson', "Guruh darsi boshlanganda shu guruh qarzdorlari ro'yxati"),
                ],
                max_length=20,
            ),
        ),
    ]
