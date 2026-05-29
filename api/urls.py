from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import GroupViewSet, StudentViewSet, PaymentViewSet, TrashViewSet

router = DefaultRouter()
router.register('groups', GroupViewSet)
router.register('students', StudentViewSet)
router.register('payments', PaymentViewSet)
router.register('trash', TrashViewSet)

urlpatterns = [
    path('', include(router.urls)),
]