import os
import sys

from django.apps import AppConfig

# Bu buyruqlar bajarilayotganda fon rejalashtiruvchisini ishga tushirmaymiz
# (migratsiya, shell, test va h.k. paytida Telegramga bexosdan xabar
# ketib qolmasligi uchun).
_SKIP_SCHEDULER_COMMANDS = {
    'migrate', 'makemigrations', 'shell', 'shell_plus', 'test',
    'collectstatic', 'createsuperuser', 'dbshell', 'showmigrations',
    'dumpdata', 'loaddata',
}


class ApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api'

    def ready(self):
        command = sys.argv[1] if len(sys.argv) > 1 else ''

        if command in _SKIP_SCHEDULER_COMMANDS:
            return

        # `runserver` avtoreload paytida ready() avval "kuzatuvchi" jarayonda,
        # so'ng haqiqiy server jarayonida (RUN_MAIN=true) chaqiriladi.
        # Faqat haqiqiy server jarayonida ishga tushiramiz — aks holda
        # rejalashtiruvchi ikki marta ishga tushib qolishi mumkin.
        if command == 'runserver' and os.environ.get('RUN_MAIN') != 'true':
            return

        from .scheduler import start_reminder_scheduler
        start_reminder_scheduler()
