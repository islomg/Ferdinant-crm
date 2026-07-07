"""
Qarzdorlarga avtomatik Telegram eslatmalarini boshqarish.

Qoida:
- Har oyning 5-sanasidan boshlab, HAR 5 KUNDA bir marta (5, 10, 15, 20, 25,
  30-sanalarda) — BARCHA o'quvchilarga qaratilgan umumiy to'lov eslatmasi
  umumiy chatga yuboriladi.
- 15-sanadan keyin (ya'ni 16-sanadan boshlab) — har bir qarzdor o'quvchi
  uchun ALOHIDA, shaxsiylashtirilgan ogohlantirish xabari yuboriladi. Agar
  qarzdorlar soni 4 tadan ko'p bo'lsa, xabarlar 4 talik guruhlarga bo'linib,
  guruhlar orasida 5 daqiqa kutilib yuboriladi.

Ikkala eslatma turi ham ANIQ SOAT 8:00 (Toshkent vaqti)da, belgilangan
sanada boshlanishi kerak — soatlik tekshiruvga tushib qolgan har qanday
payt emas. Shu bilan birga, agar server vaqtincha ishlamay qolib, aynan
8:00 daqiqasi o'tkazib yuborilgan bo'lsa ham — eslatma "kechikib" bo'lsa
ham albatta yetkazilishi kerak (rejalashtirilgan payt allaqachon o'tgan
bo'lsa va hali yuborilmagan bo'lsa, keyingi tekshiruvda darhol yuboriladi).

Har bir eslatma bir marta (o'z davri uchun) yuboriladi — buni ReminderLog
jadvali orqali kuzatamiz. Bu bir nechta gunicorn worker fon jarayoni bir
vaqtda ishlab qolsa ham, xabar takrorlanib ketmasligini kafolatlaydi
(ReminderLog.period + reminder_type unique bo'lgani uchun).
"""
import calendar
import threading
from datetime import datetime, time as dt_time

try:
    from zoneinfo import ZoneInfo
    TASHKENT_TZ = ZoneInfo("Asia/Tashkent")
except Exception:  # pragma: no cover - zoneinfo har doim mavjud bo'lishi kerak (py>=3.9)
    TASHKENT_TZ = None

from .models import Student, ReminderLog
from . import telegram_service

# Umumiy eslatma yuboriladigan sanalar (oyning 5-sanasidan boshlab, har 5 kunda).
GENERAL_DAYS = (5, 10, 15, 20, 25, 30)

# Alohida qarzdorlik ogohlantirishi 15-sanadan KEYIN, ya'ni 16-sanadan
# boshlab yuboriladi.
INDIVIDUAL_START_DAY = 16

# Ikkala eslatma ham shu soatda (Toshkent vaqti bo'yicha) boshlanishi kerak.
TRIGGER_HOUR = 8

# Individual ogohlantirishlar 4 talik guruhlarga bo'linadi, guruhlar orasida
# shuncha soniya (5 daqiqa) kutiladi.
INDIVIDUAL_BATCH_SIZE = 4
INDIVIDUAL_BATCH_PAUSE_SECONDS = 5 * 60


def _now_local():
    if TASHKENT_TZ:
        return datetime.now(TASHKENT_TZ)
    return datetime.now()


def get_debtor_students():
    return list(
        Student.objects.filter(debt_amount__gt=0).select_related('group')
    )


def _general_bucket_day(now):
    """
    Joriy sana uchun "qaysi 5-kunlik bosqichga tegishli ekanini" aniqlaydi:
    masalan oyning 7-sanasi bo'lsa, bu hali 5-sana bosqichiga tegishli (10
    kelgunga qadar). Agar oy hali 5-sanaga yetmagan bo'lsa (masalan 1-4),
    None qaytaradi — bu oy uchun umumiy eslatma bosqichi hali boshlanmagan.
    Qisqa oylar (masalan fevral)da 30-sana mavjud bo'lmasa, shu oydagi eng
    oxirgi mavjud bosqich ishlatiladi.
    """
    days_in_month = calendar.monthrange(now.year, now.month)[1]
    valid_days = [d for d in GENERAL_DAYS if d <= days_in_month]

    bucket = None
    for d in valid_days:
        if now.day >= d:
            bucket = d
    return bucket


def _scheduled_datetime(now, day):
    return datetime(
        now.year, now.month, day, TRIGGER_HOUR, 0, 0, tzinfo=now.tzinfo
    )


def check_and_send_reminders(force=False):
    """
    Joriy sanaga qarab kerakli eslatma(lar)ni yuboradi.
    `force=True` bo'lsa — shu davr uchun avval yuborilgan bo'lsa ham,
    eslatmani qayta yuborishga majburlaydi (qo'lda test qilish uchun).
    """
    # Avval, agar yangi oy boshlangan bo'lsa, o'quvchilarning qarz holatini
    # yangilaymiz — aks holda hisobot eskirgan ma'lumot bilan yuborilishi mumkin.
    from .views import ensure_monthly_reset
    ensure_monthly_reset()

    now = _now_local()
    month_period = now.strftime("%Y-%m")
    results = {}

    # ---- 1) Umumiy eslatma: har oyning 5, 10, 15, 20, 25, 30-sanalarida ----
    bucket_day = _general_bucket_day(now)
    if bucket_day is not None:
        general_period = f"{month_period}-{bucket_day:02d}"
        scheduled_at = _scheduled_datetime(now, bucket_day)

        if force:
            ReminderLog.objects.filter(
                period=general_period, reminder_type=ReminderLog.GENERAL
            ).delete()

        if now >= scheduled_at:
            results['general'] = _try_send_once(
                general_period,
                ReminderLog.GENERAL,
                lambda: telegram_service.send_general_reminder(month_period),
            )

    # ---- 2) Individual qarzdorlik ogohlantirishi: 16-sanadan boshlab ----
    scheduled_individual_at = _scheduled_datetime(now, INDIVIDUAL_START_DAY)

    if force:
        ReminderLog.objects.filter(
            period=month_period, reminder_type=ReminderLog.INDIVIDUAL
        ).delete()

    if now >= scheduled_individual_at:
        results['individual'] = _try_send_individual_once(month_period)

    return results


def _try_send_once(period, reminder_type, send_fn):
    """
    ReminderLog yordamida "shu turdagi eslatma shu davr uchun yuborilganmi"ni
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


def _try_send_individual_once(month_period):
    """
    Individual qarzdorlik ogohlantirishlarini boshlaydi. Bu yuborish
    (qarzdorlar ko'p bo'lsa) bir necha daqiqa davom etishi mumkin bo'lgani
    uchun, log darhol (yuborishdan OLDIN) yoziladi — shu orqali boshqa
    worker/tekshiruv bir vaqtda qayta boshlab yubormasligi kafolatlanadi —
    va haqiqiy yuborish alohida fon oqimida (thread) amalga oshiriladi, shu
    bilan asosiy scheduler tsikli bloklanmaydi.
    """
    log, created = ReminderLog.objects.get_or_create(
        period=month_period, reminder_type=ReminderLog.INDIVIDUAL
    )
    if not created:
        return 'already_sent'

    debtors = get_debtor_students()
    if not debtors:
        return 'no_debtors'

    def _run():
        try:
            telegram_service.send_individual_debt_warnings_batched(
                debtors,
                month_period,
                batch_size=INDIVIDUAL_BATCH_SIZE,
                batch_pause_seconds=INDIVIDUAL_BATCH_PAUSE_SECONDS,
            )
        except Exception as exc:
            print(f"[reminders] Individual eslatmalarni yuborishda xato: {exc}")

    threading.Thread(
        target=_run, name="individual-debt-reminders", daemon=True
    ).start()

    return f'sending ({len(debtors)} ta qarzdor, {INDIVIDUAL_BATCH_SIZE} talik guruhlarda)'