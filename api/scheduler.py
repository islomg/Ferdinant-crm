"""
Alohida cron/Celery infratuzilmasi qo'shmasdan, mavjud gunicorn jarayoni
ichida oddiy fon oqimi (background thread) yordamida har soatda bir marta
sana tekshiriladi. Kerakli kun kelganda (1-sana yoki 16-sanadan keyin)
Telegram eslatmasi avtomatik yuboriladi.

Bir necha marta ishga tushib ketmasligi uchun (masalan Django autoreload)
oddiy modul darajasidagi flag ishlatiladi.
"""
import threading
import time
import traceback

_scheduler_started = False
_lock = threading.Lock()

# Sana tekshiruvi orasidagi interval (soniyada). Har soatda tekshirish
# yetarli — chunki eslatmalar kun darajasida (oyning 1-sanasi / 16-sanasidan
# keyin) ishga tushadi, daqiqama-daqiqa aniqlik shart emas.
CHECK_INTERVAL_SECONDS = 60 * 60


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
