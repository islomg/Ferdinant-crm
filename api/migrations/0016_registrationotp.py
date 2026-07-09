from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0015_crmuser_role'),
    ]

    operations = [
        migrations.CreateModel(
            name='RegistrationOTP',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('verification_id', models.CharField(max_length=64, unique=True)),
                ('code', models.CharField(max_length=4)),
                ('verified', models.BooleanField(default=False)),
                ('used', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField()),
            ],
        ),
    ]
