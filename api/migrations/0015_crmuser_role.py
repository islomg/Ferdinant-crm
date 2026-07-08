from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0014_fix_group_telegram_chat_id_not_null'),
    ]

    operations = [
        migrations.AddField(
            model_name='crmuser',
            name='role',
            field=models.CharField(
                max_length=20,
                choices=[('admin', 'Admin'), ('teacher', 'Teacher')],
                default='teacher',
            ),
        ),
    ]