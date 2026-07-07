"""
Alohida cron/Celery infratuzilmasi qo'shmasdan, mavjud gunicorn jarayoni
ichida oddiy fon oqimi (background thread) yordamida muntazam ravishda
joriy sana/soat tekshiriladi. Kerakli kun va soat (ertalabki 8:00, Toshkent
vaqti) kelganda, tegishli Telegram eslatmasi avtomatik yuboriladi:
- oyning 5, 10, 15, 20, 25, 30-sanalarida — umumiy to'lov eslatmasi;
- 16-sanadan boshlab — har bir qarzdorga alohida ogohlantirish.

Bir necha marta ishga tushib ketmasligi uchun (masalan Django autoreload)
oddiy modul darajasidagi flag ishlatiladi.
"""
import threading
import time
import traceback

_scheduler_started = False
_lock = threading.Lock()

# Sana/soat tekshiruvi orasidagi interval (soniyada). Eslatmalar aniq
# soat 8:00da boshlanishi kerak bo'lgani uchun, tekshiruv har soatda emas,
# har 5 daqiqada bir marta bajariladi (shunda 8:00dan ko'pi bilan bir necha
# daqiqa kechikish bilan ishga tushadi).
CHECK_INTERVAL_SECONDS = 5 * 60


def start_reminder_scheduler():
    global _scheduler_started
    with _lock:
        if _scheduler_started:
            return
        _scheduler_started = True

    thread = threading.Thread(
        target=_run_loop, name="debt-reminder-scheduler", daemon=True
    )
    thread.start()


def _run_loop():
    # Server (va DB ulanishi) to'liq ishga tushishini biroz kutamiz.
    time.sleep(30)

    while True:
        try:
            from .reminders import check_and_send_reminders
            check_and_send_reminders()
        except Exception:
            traceback.print_exc()
        time.sleep(CHECK_INTERVAL_SECONDS)