from django.db import models
from django.utils import timezone
import secrets


class Group(models.Model):
    user = models.ForeignKey(
        'CRMUser',
        on_delete=models.CASCADE,
        related_name='groups',
        null=True,
        blank=True
    )
    name = models.CharField(max_length=100)
    time = models.CharField(max_length=10, default="15:00")
    days = models.CharField(max_length=20, default="DCHJ")
    course_type = models.CharField(max_length=100, blank=True)
    teacher = models.CharField(max_length=100, blank=True)
    price = models.IntegerField(default=500000)
    max_students = models.IntegerField(default=17)

    def __str__(self):
        return self.name


class Student(models.Model):
    name = models.CharField(max_length=200)
    group = models.ForeignKey(Group, on_delete=models.SET_NULL, null=True, blank=True)
    original_debt = models.IntegerField(default=500000)
    debt_amount = models.IntegerField(default=500000)
    paid_amount = models.IntegerField(default=0)
    payment_status = models.CharField(max_length=20, default="debt")
    # Joriy to'lov holati qaysi oyga tegishli ekanini belgilaydi, masalan "2026-07".
    # Yangi oy boshlanganda shu maydon eskirgan hisoblanib, holat reset qilinadi.
    period = models.CharField(max_length=7, blank=True, default="")

    def save(self, *args, **kwargs):

        self.debt_amount = max(
            0,
            self.original_debt - self.paid_amount
        )

        if self.debt_amount == 0:
            self.payment_status = "paid"

        elif self.paid_amount > 0:
            self.payment_status = "partial"

        else:
            self.payment_status = "debt"

        if not self.period:
            self.period = timezone.now().strftime("%Y-%m")

        super().save(*args, **kwargs)


class Payment(models.Model):
    owner = models.ForeignKey(
        'CRMUser',
        on_delete=models.PROTECT,   # user o'chsa ham payment yo'qolmasin
        related_name='payments'
    )
    student = models.ForeignKey(
        Student,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payments'
    )
    # Student o'chib ketsa ham, kim to'lagani ko'rinib tursin
    student_name_snapshot = models.CharField(max_length=255, blank=True)

    amount = models.IntegerField()
    month = models.CharField(max_length=20)
    year = models.IntegerField()
    date = models.CharField(max_length=20)

    def save(self, *args, **kwargs):
        if self.student and not self.student_name_snapshot:
            self.student_name_snapshot = self.student.name
        super().save(*args, **kwargs)


class Trash(models.Model):
    student_data = models.JSONField()
    deleted_at = models.DateTimeField(auto_now_add=True)
    from_group = models.CharField(max_length=100, blank=True)


# ===================== CRM FOYDALANUVCHILAR =====================
def generate_token():
    return secrets.token_hex(32)


class CRMUser(models.Model):
    username = models.CharField(max_length=100, unique=True)
    password_hash = models.CharField(max_length=200)
    name = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    address = models.CharField(max_length=200, blank=True)
    avatar = models.TextField(blank=True)  # base64
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.username


class CRMSession(models.Model):
    user = models.ForeignKey(CRMUser, on_delete=models.CASCADE, related_name='sessions')
    token = models.CharField(max_length=200, unique=True, default=generate_token)
    device_id = models.CharField(max_length=200, blank=True)
    is_trusted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.token[:10]}..."