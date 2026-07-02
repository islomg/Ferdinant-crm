from django.db import migrations


def backfill_payment_owner(apps, schema_editor):
    Payment = apps.get_model('api', 'Payment')

    # 1) Student hali mavjud bo'lgan (o'chirilmagan) paymentlar uchun:
    #    user va student_name_snapshotni student -> group -> user zanjiri orqali tiklaymiz.
    qs = Payment.objects.filter(
        user__isnull=True,
        student__isnull=False,
    ).select_related('student', 'student__group')

    for payment in qs:
        student = payment.student
        update_fields = []

        if not payment.student_name_snapshot:
            payment.student_name_snapshot = student.name
            update_fields.append('student_name_snapshot')

        group = getattr(student, 'group', None)
        if group and group.user_id:
            payment.user_id = group.user_id
            update_fields.append('user_id')

        if update_fields:
            payment.save(update_fields=update_fields)


def noop_reverse(apps, schema_editor):
    # Qaytarib bo'lmaydi - bu faqat ma'lumot to'ldirish, hech narsani o'chirmaymiz.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0006_payment_ownership_fixes'),
    ]

    operations = [
        migrations.RunPython(backfill_payment_owner, noop_reverse),
    ]
