"""
Qarzdorlarga avtomatik Telegram eslatmalarini boshqarish.

Qoida:
- Oyning 1-sanasidan boshlab: BARCHA qarzdorlar ro'yxati BITTA (yoki, ro'yxat
  uzun bo'lsa, bir nechta) umumiy xabar sifatida umumiy chatga yuboriladi.
- 15-sanadan keyin: har bir qarzdor o'quvchi uchun ALOHIDA ogohlantirish
  xabari umumiy chatga yuboriladi.

Har bir turdagi eslatma bir oyda faqat BIR MARTA yuboriladi — buni
ReminderLog jadvali orqali kuzatamiz. Bu bir nechta gunicorn worker fon
jarayoni bir vaqtda ishlab qolsa ham, xabar takrorlanib ketmasligini
kafolatlaydi (ReminderLog.period + reminder_type unique bo'lgani uchun).
"""
from datetime import datetime

try:
    from zoneinfo import ZoneInfo
    TASHKENT_TZ = ZoneInfo("Asia/Tashkent")
except Exception:  # pragma: no cover - zoneinfo har doim mavjud bo'lishi kerak (py>=3.9)
    TASHKENT_TZ = None

from .models import Student, ReminderLog
from . import telegram_service


def _now_local():
    if TASHKENT_TZ:
        return datetime.now(TASHKENT_TZ)
    return datetime.now()


def get_debtor_students():
    return list(
        Student.objects.filter(debt_amount__gt=0).select_related('group')
    )


def check_and_send_reminders(force=False):
    """
    Joriy sanaga qarab kerakli eslatma(lar)ni yuboradi.
    `force=True` bo'lsa — shu oy uchun avval yuborilgan bo'lsa ham,
    eslatmani qayta yuborishga majburlaydi (qo'lda test qilish uchun).
    """
    # Avval, agar yangi oy boshlangan bo'lsa, o'quvchilarning qarz holatini
    # yangilaymiz — aks holda hisobot eskirgan ma'lumot bilan yuborilishi mumkin.
    from .views import ensure_monthly_reset
    ensure_monthly_reset()

    now = _now_local()
    period = now.strftime("%Y-%m")
    day = now.day

    results = {}

    if force:
        ReminderLog.objects.filter(period=period).delete()

    if day >= 1:
        results['monthly_summary'] = _try_send_once(
            period,
            ReminderLog.MONTHLY_SUMMARY,
            lambda: telegram_service.send_monthly_summary(get_debtor_students(), period),
        )

    if day >= 16:
        results['individual'] = _try_send_once(
            period,
            ReminderLog.INDIVIDUAL,
            lambda: telegram_service.send_individual_warnings(get_debtor_students()),
        )

    return results


def _try_send_once(period, reminder_type, send_fn):
    """
    ReminderLog yordamida "shu turdagi eslatma shu oy uchun yuborilganmi"ni
    atomik tarzda tekshiradi va belgilaydi (get_or_create — bir nechta
    worker bir vaqtda chaqirsa ham faqat bittasi haqiqiy yuborishni bajaradi).
    """
    log, created = ReminderLog.objects.get_or_create(
        period=period, reminder_type=reminder_type
    )
    if not created:
        return 'already_sent'

    try:
        send_fn()
        return 'sent'
    except Exception as exc:
        # Yuborish muvaffaqiyatsiz bo'lsa, keyingi tekshiruvda qayta
        # urinib ko'rilishi uchun log yozuvini bekor qilamiz.
        log.delete()
        print(f"[reminders] Eslatma yuborishda xato ({reminder_type}): {exc}")
        return 'error'
