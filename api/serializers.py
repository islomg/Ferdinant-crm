from rest_framework import serializers
from .models import Group, Student, Payment, Trash, CRMUser, CRMSession


class GroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = '__all__'


class StudentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Student
        fields = '__all__'


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = '__all__'
        read_only_fields = ['owner']


class TrashSerializer(serializers.ModelSerializer):
    class Meta:
        model = Trash
        fields = '__all__'


class CRMUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CRMUser
        fields = ['id', 'username', 'name', 'phone', 'address', 'avatar', 'created_at']