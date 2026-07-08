from django.shortcuts import render
from rest_framework import viewsets, status
from rest_framework.decorators import api_view, action
from rest_framework.response import Response
from django.utils import timezone
from django.contrib.auth.hashers import make_password, check_password
import hashlib
import threading
from django_ratelimit.decorators import ratelimit

from .models import Group, Student, Payment, Trash, CRMUser, CRMSession
from .serializers import GroupSerializer, StudentSerializer, PaymentSerializer, TrashSerializer, CRMUserSerializer
from . import telegram_service



def notify_activity(user, title, details=""):
    """
    telegram_service.send_activity_notice'ni fon oqimida (bloklamasdan)
    chaqiradigan qulay yordamchi. `user` None bo'lishi mumkin emas deb
    kutilmaydi — shu holatda ham xatosiz "Noma'lum" deb yuboradi.
    """
    username = user.username if user else "Noma'lum"
    threading.Thread(
        target=telegram_service.send_activity_notice,
        args=(username, title, details),
        daemon=True,
    ).start()


# ===================== OYLIK RESET =====================
def ensure_monthly_reset():
    """
    Yangi oy boshlanganda:
    - Oldingi oy TO'LIQ to'langan bo'lsa -> joriy oy narxiga (guruh narxi) qarz ochiladi.
    - Oldingi oyda TO'LANMAGAN qarz qolgan bo'lsa -> u YO'QOLMAYDI,
      joriy oy narxiga QO'SHILIB, yangi original_debt hosil qilinadi.
    """
    current_period = timezone.now().strftime("%Y-%m")
    stale = Student.objects.exclude(period=current_period).select_related('group')

    for student in stale:
        unpaid_carryover = student.debt_amount or 0
        if student.group and student.group.price is not None:
            monthly_price = student.group.price
        else:
            monthly_price = student.original_debt or 0

        student.original_debt = unpaid_carryover + monthly_price
        student.paid_amount = 0
        student.debt_amount = student.original_debt
        student.payment_status = "paid" if student.original_debt == 0 else "debt"
        student.period = current_period
        student.save(update_fields=[
            "original_debt", "paid_amount", "debt_amount", "payment_status", "period"
        ])

# ===================== MAVJUD VIEWSETLAR =====================
class GroupViewSet(viewsets.ModelViewSet):
    queryset = Group.objects.all()
    serializer_class = GroupSerializer

    def get_queryset(self):
        user = get_user_from_token(self.request)

        if not user:
            return Group.objects.none()

        owner_id = self.request.query_params.get('owner_id')
        if owner_id:
            if not is_admin(user):
                return Group.objects.none()
            return Group.objects.filter(user_id=owner_id)

        return Group.objects.filter(user=user)

    def perform_create(self, serializer):
        user = get_user_from_token(self.request)

        target_user = user
        owner_id = self.request.data.get('user')
        if owner_id and is_admin(user):
            selected_user = CRMUser.objects.filter(id=owner_id).first()
            if selected_user:
                target_user = selected_user

        group = serializer.save(user=target_user)

        notify_activity(
            user,
            "Guruh qo'shildi",
            f"📚 Guruh: {group.name}"
            + (f"\n👥 Uchun: {target_user.username}" if target_user and target_user != user else ""),
        )

class StudentViewSet(viewsets.ModelViewSet):
    queryset = Student.objects.all()
    serializer_class = StudentSerializer

    def get_queryset(self):
        ensure_monthly_reset()

        user = get_user_from_token(self.request)

        if not user:
            return Student.objects.none()

        return Student.objects.filter(
            group__user=user
        )

    def perform_create(self, serializer):
        user = get_user_from_token(self.request)
        student = serializer.save()

        group_name = student.group.name if student.group else "-"
        notify_activity(
            user,
            "O'quvchi qo'shildi",
            f"🧑\u200d🎓 O'quvchi: {student.name}\n📚 Guruh: {group_name}",
        )


class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer

    def get_queryset(self):
        user = get_user_from_token(self.request)

        if not user:
            return Payment.objects.none()

        return Payment.objects.filter(owner=user)

    def perform_create(self, serializer):
        user = get_user_from_token(self.request)
        payment = serializer.save(owner=user)

        student_name = payment.student_name_snapshot or (payment.student.name if payment.student else "-")
        notify_activity(
            user,
            "To'lov kiritildi",
            f"🧑\u200d🎓 O'quvchi: {student_name}\n💵 Summa: {telegram_service.format_money(payment.amount)} so'm",
        )

    def update(self, request, *args, **kwargs):
        # Frontend to'lovni tahrirlashda barcha maydonlarni (masalan owner,
        # student_name_snapshot) jo'natmasligi mumkin. PUT so'rovini har doim
        # "partial" sifatida qabul qilamiz — shunda jo'natilmagan maydonlar
        # (jumladan ism suratini saqlaydigan student_name_snapshot) o'zgarishsiz qoladi.
        kwargs['partial'] = True
        return super().update(request, *args, **kwargs)


class TrashViewSet(viewsets.ModelViewSet):
    queryset = Trash.objects.all()
    serializer_class = TrashSerializer

    def get_queryset(self):
        user = get_user_from_token(self.request)
        if not user:
            return Trash.objects.none()
        return Trash.objects.filter(owner=user)

    def perform_create(self, serializer):
        user = get_user_from_token(self.request)
        serializer.save(owner=user)

    @action(detail=True, methods=['post'])
    def restore(self, request, pk=None):
        """O'chirilgan o'quvchini qaytarish"""
        user = get_user_from_token(request)
        if not user:
            return Response({'error': "Avtorizatsiya talab qilinadi"}, status=401)

        try:
            trash_item = Trash.objects.get(id=pk, owner=user)
        except Trash.DoesNotExist:
            return Response({'error': 'Topilmadi'}, status=404)

        student_data = trash_item.student_data
        # id ni olib tashlaymiz — yangi id berilsin
        student_data.pop('id', None)
        # group FK ni to'g'ri ko'rinishda saqlash
        group_id = student_data.pop('group', None)

        # Agar frontend o'quvchini ATAYLAB boshqa guruhga biriktirmoqchi bo'lsa
        # (masalan, asl guruh o'chirilgani uchun modal orqali yangi guruh tanlangan),
        # shu guruh ustuvor bo'ladi.
        new_group_id = request.data.get('new_group_id')

        group = None
        if new_group_id:
            group = Group.objects.filter(id=new_group_id, user=user).first()
            if not group:
                return Response(
                    {'error': 'invalid_group', 'message': "Tanlangan guruh topilmadi."},
                    status=400
                )
        elif group_id:
            # O'quvchi qaysi guruhga tegishli bo'lsa, o'sha guruh hali ham mavjudligini tekshiramiz.
            # Agar guruh o'chirilgan bo'lsa, o'quvchini guruhsiz yoki noto'g'ri guruhga qaytarish
            # o'rniga frontendga aniq xato qaytaramiz — u yerda foydalanuvchiga modal orqali
            # boshqa guruh tanlash imkoniyati beriladi. Agar guruh hali mavjud bo'lsa,
            # o'quvchi o'zining eski guruhiga qaytariladi.
            group = Group.objects.filter(id=group_id, user=user).first()
            if not group:
                return Response(
                    {
                        'error': 'group_deleted',
                        'message': "Bu o'quvchi tegishli bo'lgan guruh o'chirib yuborilgan. "
                                   "Avval guruhni tiklang yoki o'quvchini boshqa guruhga biriktiring."
                    },
                    status=409
                )

        try:
            student = Student(
                name=student_data.get('name', ''),
                original_debt=student_data.get('original_debt', 500000),
                debt_amount=student_data.get('debt_amount', 500000),
                paid_amount=student_data.get('paid_amount', 0),
                payment_status=student_data.get('payment_status', 'debt'),
            )
            if group:
                student.group = group
            student.save()
            trash_item.delete()
            return Response(StudentSerializer(student).data)
        except Exception as e:
            return Response({'error': str(e)}, status=400)


# ===================== YORDAMCHI =====================
def hash_password(password):
    # Django'ning PBKDF2 (avtomatik salt bilan) hash'lash mexanizmi —
    # xom sha256'ga qaraganda ancha xavfsiz.
    return make_password(password)


def verify_password(user, password):
    """
    Parolni tekshiradi. Eski (salt'siz sha256) va yangi (Django PBKDF2)
    formatlarni ham qo'llab-quvvatlaydi. Agar foydalanuvchining paroli
    hali eski formatda bo'lsa va to'g'ri kiritilsa — uni shu yerdayoq
    xavfsiz formatga o'tkazib, bazaga saqlab qo'yamiz (shaffof migratsiya,
    foydalanuvchi parolini qayta o'rnatishi shart emas).
    """
    stored = user.password_hash

    if stored.startswith(('pbkdf2_', 'bcrypt', 'argon2')):
        return check_password(password, stored)

    legacy_hash = hashlib.sha256(password.encode()).hexdigest()
    if legacy_hash == stored:
        user.password_hash = make_password(password)
        user.save(update_fields=['password_hash'])
        return True

    return False


def is_admin(user):
    """Foydalanuvchi admin rolidami — tekshiradi."""
    return bool(user) and getattr(user, 'role', None) == CRMUser.ROLE_ADMIN


def get_user_from_token(request):
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    if not token:
        return None
    try:
        session = CRMSession.objects.select_related('user').get(token=token)
        session.last_used = timezone.now()
        session.save(update_fields=['last_used'])
        return session.user
    except CRMSession.DoesNotExist:
        return None


# ===================== AUTH API =====================

@api_view(['GET'])
def auth_check_has_users(request):
    """Tizimda foydalanuvchilar bormi — token talab qilmaydi"""
    count = CRMUser.objects.count()
    return Response({'has_users': count > 0, 'count': count})

@api_view(['POST'])
@ratelimit(key='ip', rate='10/m', block=True)
def auth_register(request):
    """Yangi foydalanuvchi ro'yxatdan o'tish"""
    username = request.data.get('username', '').strip().lower()
    password = request.data.get('password', '')
    device_id = request.data.get('device_id', '')

    if not username or not password:
        return Response({'error': 'Login va parol kiritilishi shart'}, status=400)

    if len(password) < 4:
        return Response({'error': "Parol kamida 4 ta belgi bo'lishi kerak"}, status=400)

    if CRMUser.objects.filter(username=username).exists():
        return Response({'error': 'Bu login allaqachon band'}, status=400)

    user = CRMUser.objects.create(
        username=username,
        password_hash=hash_password(password)
    )

    # Session yaratish — ro'yxatdan o'tgach OTP tasdiqlanadi, keyin is_trusted=True bo'ladi
    session = CRMSession.objects.create(
        user=user,
        device_id=device_id,
        is_trusted=False  # OTP tasdiqlanguncha False
    )

    return Response({
        'token': session.token,
        'user': CRMUserSerializer(user).data
    })


@api_view(['POST'])
@ratelimit(key='ip', rate='5/m', block=True)
@ratelimit(key='post:username', rate='5/m', block=True)
def auth_login(request):
    """Login"""
    username = request.data.get('username', '').strip().lower()
    password = request.data.get('password', '')
    device_id = request.data.get('device_id', '')

    if not username or not password:
        return Response({'error': 'Login va parol kiritilishi shart'}, status=400)

    try:
        user = CRMUser.objects.get(username=username)
    except CRMUser.DoesNotExist:
        return Response({'error': "Login yoki parol noto'g'ri"}, status=401)

    if not verify_password(user, password):
        return Response({'error': "Login yoki parol noto'g'ri"}, status=401)

    # Avvalgi sessionlarda shu device ishonchli bo'lganmi?
    is_trusted = CRMSession.objects.filter(
        user=user,
        device_id=device_id,
        is_trusted=True
    ).exists()

    # Yangi session yaratish
    session = CRMSession.objects.create(
        user=user,
        device_id=device_id,
        is_trusted=is_trusted  # Ishonchli qurilma bo'lsa darhol True
    )

    # Kirish haqida Telegram botga xabar yuboramiz (javobni kutdirmasligi uchun fon oqimida)
    import threading
    from . import telegram_service
    client_ip = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() or request.META.get('REMOTE_ADDR', '')
    threading.Thread(
        target=telegram_service.send_user_login_notice,
        args=(user,),
        kwargs={'device_id': device_id, 'is_trusted': is_trusted, 'ip_address': client_ip},
        daemon=True,
    ).start()

    return Response({
        'token': session.token,
        'is_trusted': is_trusted,
        'user': CRMUserSerializer(user).data
    })


@api_view(['POST'])
def auth_trust_device(request):
    """Qurilmani ishonchli qilish (OTP tasdiqlangandan keyin)"""
    user = get_user_from_token(request)
    if not user:
        return Response({'error': "Token noto'g'ri"}, status=401)

    device_id = request.data.get('device_id', '')
    token = request.headers.get('Authorization', '').replace('Bearer ', '')

    # Joriy sessionni ishonchli qilish
    CRMSession.objects.filter(token=token).update(is_trusted=True)

    # Shu device_id li barcha sessionlarni ishonchli qilish
    if device_id:
        CRMSession.objects.filter(user=user, device_id=device_id).update(is_trusted=True)

    return Response({'ok': True})


@api_view(['POST'])
def auth_logout(request):
    """Chiqish — sessionni o'chirish"""
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    if token:
        session = CRMSession.objects.filter(token=token).select_related('user').first()
        if session:
            username = session.user.username
            session.delete()

            # Chiqish haqida Telegram botga xabar yuboramiz (fon oqimida)
            import threading
            from . import telegram_service
            threading.Thread(
                target=telegram_service.send_user_logout_notice,
                args=(username,),
                daemon=True,
            ).start()
    return Response({'ok': True})


@api_view(['POST'])
def auth_site_enter(request):
    """
    Foydalanuvchi saytni brauzerda ochganda chaqiriladi (masalan, token orqali
    avtomatik kirganda — parol qayta so'ralmaydi). Har safar sayt ochilganda
    Telegram botga "Saytga kirdi" xabari yuboriladi.
    """
    user = get_user_from_token(request)
    if not user:
        return Response({'error': "Token noto'g'ri"}, status=401)

    device_id = request.data.get('device_id', '')
    client_ip = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() or request.META.get('REMOTE_ADDR', '')

    import threading
    from . import telegram_service
    threading.Thread(
        target=telegram_service.send_site_enter_notice,
        args=(user,),
        kwargs={'device_id': device_id, 'ip_address': client_ip},
        daemon=True,
    ).start()
    return Response({'ok': True})


@api_view(['POST'])
def auth_site_leave(request):
    """
    Foydalanuvchi brauzer/tabni yopganda yoki sahifadan chiqib ketganda
    chaqiriladi (navigator.sendBeacon orqali). sendBeacon Authorization
    header qo'sha olmaydi, shuning uchun token requestning o'zida keladi.
    """
    token = request.data.get('token', '')
    if not token:
        return Response({'error': "Token yo'q"}, status=400)

    session = CRMSession.objects.filter(token=token).select_related('user').first()
    if not session:
        return Response({'error': "Token noto'g'ri"}, status=401)

    username = session.user.username

    import threading
    from . import telegram_service
    threading.Thread(
        target=telegram_service.send_site_leave_notice,
        args=(username,),
        daemon=True,
    ).start()
    return Response({'ok': True})


@api_view(['GET'])
def auth_me(request):
    """Joriy foydalanuvchi ma'lumotlari"""
    user = get_user_from_token(request)
    if not user:
        return Response({'error': 'Avtorizatsiya talab qilinadi'}, status=401)
    return Response(CRMUserSerializer(user).data)


@api_view(['PUT'])
def auth_update_profile(request):
    """Profil ma'lumotlarini yangilash"""
    user = get_user_from_token(request)
    if not user:
        return Response({'error': 'Avtorizatsiya talab qilinadi'}, status=401)

    if 'name' in request.data:
        user.name = request.data['name']
    if 'phone' in request.data:
        user.phone = request.data['phone']
    if 'address' in request.data:
        user.address = request.data['address']
    if 'avatar' in request.data:
        user.avatar = request.data['avatar']

    user.save()
    return Response(CRMUserSerializer(user).data)


@api_view(['POST'])
def auth_change_password(request):
    """Parol o'zgartirish"""
    user = get_user_from_token(request)
    if not user:
        return Response({'error': 'Avtorizatsiya talab qilinadi'}, status=401)

    old_password = request.data.get('old_password', '')
    new_password = request.data.get('new_password', '')

    if not verify_password(user, old_password):
        return Response({'error': "Joriy parol noto'g'ri"}, status=400)

    if len(new_password) < 4:
        return Response({'error': "Yangi parol kamida 4 ta belgi bo'lishi kerak"}, status=400)

    user.password_hash = hash_password(new_password)
    user.save()

    return Response({'ok': True})


@api_view(['GET'])
def auth_users_list(request):
    """Barcha foydalanuvchilar ro'yxati — faqat admin"""
    user = get_user_from_token(request)
    if not user:
        return Response({'error': 'Avtorizatsiya talab qilinadi'}, status=401)
    if not is_admin(user):
        return Response({'error': "Bu amal uchun admin huquqi kerak"}, status=403)

    users = CRMUser.objects.all()
    return Response(CRMUserSerializer(users, many=True).data)


@api_view(['DELETE'])
def auth_delete_user(request, user_id):
    """Foydalanuvchini o'chirish — faqat admin"""
    current_user = get_user_from_token(request)
    if not current_user:
        return Response({'error': 'Avtorizatsiya talab qilinadi'}, status=401)
    if not is_admin(current_user):
        return Response({'error': "Bu amal uchun admin huquqi kerak"}, status=403)

    if current_user.id == user_id:
        return Response({'error': "O'zingizni o'chira olmaysiz"}, status=400)

    try:
        target = CRMUser.objects.get(id=user_id)
        target.delete()
        return Response({'ok': True})
    except CRMUser.DoesNotExist:
        return Response({'error': 'Foydalanuvchi topilmadi'}, status=404)


@api_view(['POST'])
def auth_add_user(request):
    """Yangi foydalanuvchi qo'shish — faqat admin"""
    current_user = get_user_from_token(request)
    if not current_user:
        return Response({'error': 'Avtorizatsiya talab qilinadi'}, status=401)
    if not is_admin(current_user):
        return Response({'error': "Bu amal uchun admin huquqi kerak"}, status=403)

    username = request.data.get('username', '').strip().lower()

# ===================== TELEGRAM — QARZDORLIK OGOHLANTIRISHI (QO'LDA) =====================

@api_view(['POST'])
def telegram_send_debt_warning(request):
    """
    Qarzdorlar bo'limidagi tugma orqali, xohlagan vaqtda qo'lda chaqiriladi.
    Bu avtomatik oylik eslatmadan (reminders.py) MUSTAQIL ishlaydi — ya'ni
    ReminderLog cheklovi bunga taalluqli emas, shuning uchun admin xohlagan
    vaqtida bosishi mumkin.

    Body: { "mode": "summary" | "individual" }
      - "summary"    -> barcha qarzdorlar ro'yxati BITTA xabar sifatida yuboriladi
      - "individual" -> har bir qarzdor uchun ALOHIDA xabar yuboriladi
    """
    user = get_user_from_token(request)
    if not user:
        return Response({'error': 'Avtorizatsiya talab qilinadi'}, status=401)

    mode = request.data.get('mode')
    if mode not in ('summary', 'individual'):
        return Response({'error': "mode 'summary' yoki 'individual' bo'lishi kerak"}, status=400)

    import threading
    from datetime import datetime
    from . import telegram_service
    from .reminders import get_debtor_students

    period_label = datetime.now().strftime('%Y-%m')

    if mode == 'summary':
        # Bu xabar bitta va tezkor — sinxron yuboramiz, xatoni darhol qaytarish mumkin.
        ok = telegram_service.send_general_reminder(period_label)
        if not ok:
            detail = telegram_service.get_last_error() or "Noma'lum xato"
            return Response(
                {'error': f"Telegramga yuborishda xato: {detail}"},
                status=502,
            )
        return Response({'ok': True, 'mode': mode})

    # mode == 'individual'
    debtors = get_debtor_students()
    if not debtors:
        return Response({'ok': True, 'sent': 0, 'message': "Qarzdorlar yo'q — xabar yuborilmadi"})

    # Qarzdorlar ko'p bo'lsa, 4 talik guruhlar orasida 5 daqiqa kutiladi —
    # shuning uchun so'rovni bloklamaslik uchun fon oqimida yuboramiz.
    threading.Thread(
        target=telegram_service.send_individual_debt_warnings_batched,
        args=(debtors, period_label),
        kwargs={'batch_size': 4, 'batch_pause_seconds': 5 * 60},
        daemon=True,
    ).start()

    return Response({
        'ok': True,
        'sent': len(debtors),
        'mode': mode,
        'message': (
            f"{len(debtors)} ta qarzdorga xabar yuborish boshlandi "
            "(4 talik guruhlarda, guruhlar orasida 5 daqiqa oralig'ida)."
        ),
    })


@api_view(['POST'])
def telegram_send_group_debt_warning(request):
    """
    Berilgan guruh (group_id) uchun qarzdorlar ro'yxatini, o'sha guruh
    uchun sozlangan Telegram chatiga darhol yuboradi (dars vaqtini
    kutmasdan, qo'lda test qilish yoki majburan yuborish uchun).

    Body: { "group_id": <int> }
    """
    user = get_user_from_token(request)
    if not user:
        return Response({'error': 'Avtorizatsiya talab qilinadi'}, status=401)

    group_id = request.data.get('group_id')
    if not group_id:
        return Response({'error': "'group_id' majburiy"}, status=400)

    from .models import Group, Student
    from . import telegram_service

    try:
        group = Group.objects.get(pk=group_id)
    except Group.DoesNotExist:
        return Response({'error': "Bunday guruh topilmadi"}, status=404)

    debtors = list(Student.objects.filter(group=group, debt_amount__gt=0))
    if not debtors:
        return Response({'ok': True, 'sent': 0, 'message': "Bu guruhda qarzdor yo'q"})

    ok = telegram_service.send_group_lesson_debtors(group, debtors)
    if not ok:
        detail = telegram_service.get_last_error() or "Noma'lum xato"
        return Response(
            {'error': f"Telegramga yuborishda xato: {detail}"},
            status=502,
        )

    return Response({'ok': True, 'sent': len(debtors), 'group': group.name})


@api_view(['POST'])
def telegram_send_current_lesson_warning(request):
    """
    Qarzdorlar bo'limidagi 3-tugma: joriy vaqtga qarab, HOZIR darsi davom
    etayotgan barcha guruhlarni aniqlaydi (boshlanish_vaqti <= hozirgi_vaqt
    < tugash_vaqti, har bir dars 1,5 soat davom etadi deb hisoblanadi), so'ng
    shu guruhlardagi BARCHA o'quvchilarga (qarzdorligidan qat'i nazar)
    Telegram orqali alohida ogohlantirish xabarini yuboradi.

    Individual oylik qarzdorlik ogohlantirishidan farqli o'laroq, bu yerda
    5 daqiqalik guruh-oralig'i kutish YO'Q — barcha o'quvchilarga bir vaqtda
    (ketma-ket, deyarli kutilmasdan) yuboriladi. Shunga qaramay, so'rovni
    bloklamaslik uchun yuborish fon oqimida ishga tushiriladi.
    """
    user = get_user_from_token(request)
    if not user:
        return Response({'error': 'Avtorizatsiya talab qilinadi'}, status=401)

    import threading
    from . import telegram_service
    from .reminders import get_current_lesson_students

    students = get_current_lesson_students()
    if not students:
        return Response({
            'ok': True,
            'sent': 0,
            'message': "Hozir darsi davom etayotgan guruh topilmadi",
        })

    threading.Thread(
        target=telegram_service.send_current_lesson_warnings_batched,
        args=(students,),
        daemon=True,
    ).start()

    return Response({
        'ok': True,
        'sent': len(students),
        'message': (
            f"{len(students)} ta o'quvchiga xabar yuborish boshlandi "
            "(4 talik guruhlarda, guruhlar orasida 5 daqiqa oralig'ida)."
        ),
    })

def ratelimited_error(request, exception):
    from rest_framework.response import Response
    from django.http import JsonResponse
    return JsonResponse(
        {'error': "Juda ko'p urinish qilindi. Iltimos, 1 daqiqadan keyin qayta urinib ko'ring."},
        status=429
    )