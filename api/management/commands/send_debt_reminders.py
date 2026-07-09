from django.core.management.base import BaseCommand

from api.reminders import (
    check_and_send_reminders,
    check_and_send_group_lesson_reminders,
)


class Command(BaseCommand):
    help = (
        "Qarzdorlarga Telegram orqali eslatma yuborish holatini tekshiradi va, "
        "vaqti kelgan bo'lsa, yuboradi:\n"
        "  1) Oyning 5, 10, 15, 20, 25, 30-sanalarida soat 8:00da — umumiy "
        "to'lov eslatmasi;\n"
        "  2) 16-sanadan boshlab soat 8:00da — har bir qarzdorga alohida "
        "ogohlantirish;\n"
        "  3) Har bir guruhning darsi boshlanganda (guruh jadvaliga qarab) — "
        "o'sha guruhdagi qarzdorlar ro'yxati o'sha guruh chatiga.\n"
        "Bu buyruq TASHQI CRON orqali (masalan Railway'ning 'Cron Job' "
        "xizmati yoki Heroku Scheduler) muntazam (masalan har 5-15 daqiqada) "
        "chaqirilishi uchun mo'ljallangan — shu tarzda serverning uzluksiz "
        "ishlab turishiga bog'liq bo'lmaydi. Bir marta yuborilgan eslatma "
        "ReminderLog orqali kuzatilgani uchun, buyruqni qayta-qayta ishga "
        "tushirish xavfsiz — takroriy xabar yuborilmaydi."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help="Shu davr uchun eslatma avval yuborilgan bo'lsa ham, majburan qayta yuboradi (test uchun).",
        )

    def handle(self, *args, **options):
        force = options['force']

        results = check_and_send_reminders(force=force)
        if not results:
            self.stdout.write("Bugun uchun umumiy/individual eslatma yo'q.")
        for reminder_type, status in results.items():
            self.stdout.write(f"{reminder_type}: {status}")

        group_results = check_and_send_group_lesson_reminders(force=force)
        if not group_results:
            self.stdout.write("Hozir boshlanadigan/boshlangan dars topilmadi.")
        for group_id, status in group_results.items():
            self.stdout.write(f"group #{group_id}: {status}")

        self.stdout.write(self.style.SUCCESS("Tekshiruv yakunlandi."))