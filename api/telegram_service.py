"""
Qarzdorlik eslatmalarini Telegramga yuborish uchun yordamchi funksiyalar.

Alohida kutubxona (masalan `python-telegram-bot`) qo'shmaslik uchun
standart `urllib` yordamida to'g'ridan-to'g'ri Telegram Bot API'ga
so'rov yuboriladi — xuddi frontenddagi OTP/sertifikat yuborish
kodida qilingani kabi.
"""
import json
import time
import urllib.request
import urllib.error

from django.conf import settings

# Oxirgi muvaffaqiyatsiz urinishning aniq sababini saqlab turadi (masalan,
# Telegram'ning o'zi qaytargan "chat not found" yoki "bot was kicked" kabi
# xabarlari) — shu orqali admin panelida yoki loglarda haqiqiy sababni
# ko'rsatish mumkin bo'ladi.
_last_error = {"message": None}


def get_last_error():
    """Eng oxirgi yuborish xatosining Telegram'dan kelgan aniq matnini qaytaradi."""
    return _last_error["message"]


def send_telegram_message(text, chat_id=None):
    """
    Telegramga oddiy matnli xabar yuboradi.
    Xato yuz bersa, dasturni to'xtatmasdan False qaytaradi, xatoni logga
    yozadi va get_last_error() orqali olish uchun saqlab qo'yadi.
    """
    token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
    target_chat_id = chat_id or getattr(settings, 'TELEGRAM_GROUP_CHAT_ID', '')

    if not token or not target_chat_id:
        _last_error["message"] = "BOT_TOKEN yoki CHAT_ID sozlanmagan"
        print(f"[telegram] {_last_error['message']} — xabar yuborilmadi.")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps({
        "chat_id": target_chat_id,
        "text": text,
        "parse_mode": "HTML",
    }).encode("utf-8")

    request = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            response.read()
        _last_error["message"] = None
        return True
    except urllib.error.HTTPError as exc:
        # Telegram HTTP xato bilan birga JSON tanasida aniq sababni qaytaradi
        # (masalan {"ok":false,"error_code":400,"description":"Bad Request: chat not found"}).
        # Bu — eng foydali qism, shuning uchun uni o'qib, saqlab qo'yamiz.
        try:
            body = exc.read().decode("utf-8", errors="replace")
            parsed = json.loads(body)
            description = parsed.get("description", body)
        except Exception:
            description = str(exc)
        _last_error["message"] = f"Telegram xatosi ({exc.code}): {description}"
        print(f"[telegram] {_last_error['message']}")
        return False
    except urllib.error.URLError as exc:
        _last_error["message"] = f"Ulanish xatosi: {exc.reason}"
        print(f"[telegram] Xabar yuborishda xato: {exc}")
        return False


def format_money(amount):
    try:
        return f"{int(amount):,}".replace(",", " ")
    except (TypeError, ValueError):
        return str(amount)


def _split_into_chunks(lines, header, max_len=3500):
    """
    Telegram xabar uzunligi cheklovidan (4096 belgi) xavfsiz masofada
    qolish uchun uzun ro'yxatlarni bir nechta xabarga bo'lib chiqadi.
    """
    chunks = []
    current = header
    for line in lines:
        candidate = current + "\n" + line
        if len(candidate) > max_len:
            chunks.append(current)
            current = header + " (davomi)\n" + line
        else:
            current = candidate
    chunks.append(current)
    return chunks


def send_monthly_summary(debtor_students, period_label):
    """
    Oyning boshida — barcha qarzdor o'quvchilar ro'yxatini umumiy chatga
    yuboradi. Ro'yxat uzun bo'lsa, bir nechta xabarga bo'linadi.
    """
    if not debtor_students:
        return send_telegram_message(
            f"✅ {period_label} — bu oy uchun qarzdor o'quvchilar yo'q."
        )

    header = f"📊 <b>{period_label} — QARZDORLAR RO'YXATI</b>"
    lines = []
    for i, student in enumerate(debtor_students, start=1):
        group_name = student.group.name if student.group else "guruhsiz"
        lines.append(
            f"{i}. {student.name} — {group_name} — {format_money(student.debt_amount)} so'm"
        )
    lines.append(f"\nJami: {len(debtor_students)} ta o'quvchi qarzdor.")

    chunks = _split_into_chunks(lines, header)
    ok = True
    for chunk in chunks:
        if not send_telegram_message(chunk):
            ok = False
        time.sleep(0.3)
    return ok


def send_individual_warnings(debtor_students):
    """
    15-sanadan keyin — har bir qarzdor o'quvchi uchun alohida ogohlantirish
    xabarini umumiy chatga yuboradi.
    """
    ok = True
    for student in debtor_students:
        group_name = student.group.name if student.group else "guruhsiz"
        text = (
            "⚠️ <b>Qarzdorlik ogohlantirishi</b>\n\n"
            f"👤 O'quvchi: <b>{student.name}</b>\n"
            f"👥 Guruh: {group_name}\n"
            f"💰 Qarz: {format_money(student.debt_amount)} so'm\n\n"
            "Iltimos, imkon qadar tezroq to'lovni amalga oshiring."
        )
        if not send_telegram_message(text):
            ok = False
        time.sleep(0.3)
    return ok