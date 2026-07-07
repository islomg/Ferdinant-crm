from django.core.management.base import BaseCommand

from api.reminders import check_and_send_reminders


class Command(BaseCommand):
    help = (
        "Qarzdorlarga Telegram orqali eslatma yuborish holatini tekshiradi va, "
        "sana/soat mos kelsa (oyning 5, 10, 15, 20, 25, 30-sanalari — soat "
        "8:00da umumiy eslatma; 16-sanadan boshlab — soat 8:00da har bir "
        "qarzdorga alohida ogohlantirish), eslatmani yuboradi. Odatda bu "
        "avtomatik fon jarayoni tomonidan bajariladi; bu buyruq asosan "
        "qo'lda test qilish yoki tashqi cron (masalan Railway/Heroku Scheduler) "
        "orqali chaqirish uchun mo'ljallangan."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help="Shu davr uchun eslatma avval yuborilgan bo'lsa ham, majburan qayta yuboradi (test uchun).",
        )

    def handle(self, *args, **options):
        results = check_and_send_reminders(force=options['force'])
        if not results:
            self.stdout.write("Bugun uchun yuboriladigan eslatma yo'q.")
        for reminder_type, status in results.items():
            self.stdout.write(f"{reminder_type}: {status}")
        self.stdout.write(self.style.SUCCESS("Tekshiruv yakunlandi."))