from django.db import migrations


def drop_not_null(apps, schema_editor):
    """
    Production (Postgres) bazasida 'api_group' jadvalida hozirgi Django
    modelida umuman yo'q bo'lgan 'telegram_chat_id' ustuni bor edi va u
    NOT NULL edi — shu sabab yangi guruh qo'shishda IntegrityError chiqib
    turgan edi. Bu migratsiya, agar shu ustun mavjud bo'lsa, undan
    NOT NULL cheklovini olib tashlaydi.

    Faqat Postgres uchun ishlaydi va ustun mavjudligini oldindan tekshiradi
    — shu sababli lokal SQLite muhitida yoki ustun umuman bo'lmagan
    bazalarda xavfsiz, hech narsa qilmaydi.
    """
    if schema_editor.connection.vendor != 'postgresql':
        return

    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'api_group' AND column_name = 'telegram_chat_id'
            """
        )
        if cursor.fetchone():
            cursor.execute(
                "ALTER TABLE api_group ALTER COLUMN telegram_chat_id DROP NOT NULL;"
            )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0013_reminderlog_group_lesson_type'),
    ]

    operations = [
        migrations.RunPython(drop_not_null, noop_reverse),
    ]
