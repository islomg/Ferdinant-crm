from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    GroupViewSet, StudentViewSet, PaymentViewSet, TrashViewSet,
    auth_register, auth_login, auth_trust_device, auth_logout,
    auth_me, auth_update_profile, auth_change_password,
    auth_users_list, auth_delete_user, auth_add_user,
    auth_check_has_users, telegram_send_debt_warning,
)

router = DefaultRouter()
router.register(r'groups', GroupViewSet)
router.register(r'students', StudentViewSet)
router.register(r'payments', PaymentViewSet, basename='payments')
router.register(r'trash', TrashViewSet)

urlpatterns = [
    path('', include(router.urls)),

    # Auth endpoints
    path('auth/check-users/', auth_check_has_users),   # Token talab qilmaydi
    path('auth/register/', auth_register),
    path('auth/login/', auth_login),
    path('auth/trust-device/', auth_trust_device),
    path('auth/logout/', auth_logout),
    path('auth/me/', auth_me),
    path('auth/profile/', auth_update_profile),
    path('auth/change-password/', auth_change_password),
    path('auth/users/', auth_users_list),
    path('auth/users/<int:user_id>/', auth_delete_user),
    path('auth/add-user/', auth_add_user),

    # Telegram — qarzdorlik ogohlantirishini qo'lda yuborish
    path('telegram/send-debt-warning/', telegram_send_debt_warning),
]