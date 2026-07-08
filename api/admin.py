from django.contrib import admin

from django.contrib import admin
from .models import Group, Student, Payment, Trash

@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'teacher', 'time', 'days', 'price', 'max_students')
    search_fields = ('name', 'teacher')

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'group', 'original_debt', 'debt_amount', 'paid_amount', 'payment_status')
    search_fields = ('name',)
    list_filter = ('group', 'payment_status')

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'student', 'amount', 'month', 'year', 'date')
    search_fields = ('student__name',)
    list_filter = ('month', 'year')

@admin.register(Trash)
class TrashAdmin(admin.ModelAdmin):
    list_display = ('id', 'from_group', 'deleted_at')
    search_fields = ('from_group',)