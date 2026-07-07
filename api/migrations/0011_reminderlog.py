from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0010_student_created_at'),
    ]

    operations = [
        migrations.CreateModel(
            name='ReminderLog',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('period', models.CharField(max_length=7)),
                ('reminder_type', models.CharField(
                    choices=[
                        ('monthly_summary', "Oy boshidagi umumiy qarzdorlar ro'yxati"),
                        ('individual', "15-sanadan keyingi har bir o'quvchiga alohida ogohlantirish"),
                    ],
                    max_length=20,
                )),
                ('sent_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'unique_together': {('period', 'reminder_type')},
            },
        ),
    ]
