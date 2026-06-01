from django.shortcuts import render
from rest_framework import viewsets, status
from rest_framework.decorators import api_view, action
from rest_framework.response import Response
from django.utils import timezone
import hashlib

from .models import Group, Student, Payment, Trash, CRMUser, CRMSession
from .serializers import GroupSerializer, StudentSerializer, PaymentSerializer, TrashSerializer, CRMUserSerializer


# ===================== MAVJUD VIEWSETLAR =====================
class GroupViewSet(viewsets.ModelViewSet):
    queryset = Group.objects.all()
    serializer_class = GroupSerializer


class StudentViewSet(viewsets.ModelViewSet):
    queryset = Student.objects.all()
    serializer_class = StudentSerializer


class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer


class TrashViewSet(viewsets.ModelViewSet):
    queryset = Trash.objects.all()
    serializer_class = TrashSerializer

    @action(detail=True, methods=['post'])
    def restore(self, request, pk=None):
        """O'chirilgan o'quvchini qaytarish"""
        try:
            trash_item = Trash.objects.get(id=pk)
        except Trash.DoesNotExist:
            return Response({'error': 'Topilmadi'}, status=404)

        student_data = trash_item.student_data
        # id ni olib tashlaymiz — yangi id berilsin
        student_data.pop('id', None)
        # group FK ni to'g'ri ko'rinishda saqlash
        group_id = student_data.pop('group', None)

        try:
            student = Student(
                name=student_data.get('name', ''),
                original_debt=student_data.get('original_debt', 500000),
                debt_amount=student_data.get('debt_amount', 500000),
                paid_amount=student_data.get('paid_amount', 0),
                payment_status=student_data.get('payment_status', 'debt'),
            )
            if group_id:
                try:
                    student.group_id = group_id
                except Exception:
                    student.group = None
            student.save()
            trash_item.delete()
            return Response(StudentSerializer(student).data)
        except Exception as e:
            return Response({'error': str(e)}, status=400)


# ===================== YORDAMCHI =====================
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


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

    if user.password_hash != hash_password(password):
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
        CRMSession.objects.filter(token=token).delete()
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

    if user.password_hash != hash_password(old_password):
        return Response({'error': "Joriy parol noto'g'ri"}, status=400)

    if len(new_password) < 4:
        return Response({'error': "Yangi parol kamida 4 ta belgi bo'lishi kerak"}, status=400)

    user.password_hash = hash_password(new_password)
    user.save()

    return Response({'ok': True})


@api_view(['GET'])
def auth_users_list(request):
    """Barcha foydalanuvchilar ro'yxati"""
    user = get_user_from_token(request)
    if not user:
        return Response({'error': 'Avtorizatsiya talab qilinadi'}, status=401)

    users = CRMUser.objects.all()
    return Response(CRMUserSerializer(users, many=True).data)


@api_view(['DELETE'])
def auth_delete_user(request, user_id):
    """Foydalanuvchini o'chirish"""
    current_user = get_user_from_token(request)
    if not current_user:
        return Response({'error': 'Avtorizatsiya talab qilinadi'}, status=401)

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
    """Yangi foydalanuvchi qo'shish (admin tomonidan)"""
    current_user = get_user_from_token(request)
    if not current_user:
        return Response({'error': 'Avtorizatsiya talab qilinadi'}, status=401)

    username = request.data.get('username', '').strip().lower()
    password = request.data.get('password', '')

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

    return Response(CRMUserSerializer(user).data)