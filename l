[1mdiff --git a/api/views.py b/api/views.py[m
[1mindex a90cc2f..9202dfe 100644[m
[1m--- a/api/views.py[m
[1m+++ b/api/views.py[m
[36m@@ -1,4 +1,5 @@[m
 from django.shortcuts import render[m
[32m+[m[32mfrom django.conf import settings[m
 from rest_framework import viewsets, status[m
 from rest_framework.decorators import api_view, action[m
 from rest_framework.response import Response[m
[36m@@ -267,8 +268,21 @@[m [mdef is_admin(user):[m
     return bool(user) and getattr(user, 'role', None) == CRMUser.ROLE_ADMIN[m
 [m
 [m
[32m+[m[32mdef get_session_token(request):[m
[32m+[m[32m    """[m
[32m+[m[32m    Sessiya tokenini o'qiydi. Yagona manba — httpOnly cookie (JS orqali[m
[32m+[m[32m    o'qib/o'g'irlab bo'lmaydi). Eski frontendlar bilan orqaga moslik uchun[m
[32m+[m[32m    Authorization header ham fallback sifatida qabul qilinadi, lekin yangi[m
[32m+[m[32m    frontend endi faqat cookie ishlatadi.[m
[32m+[m[32m    """[m
[32m+[m[32m    token = request.COOKIES.get(settings.AUTH_COOKIE_NAME, '')[m
[32m+[m[32m    if not token:[m
[32m+[m[32m        token = request.headers.get('Authorization', '').replace('Bearer ', '')[m
[32m+[m[32m    return token[m
[32m+[m
[32m+[m
 def get_user_from_token(request):[m
[31m-    token = request.headers.get('Authorization', '').replace('Bearer ', '')[m
[32m+[m[32m    token = get_session_token(request)[m
     if not token:[m
         return None[m
     try:[m
[36m@@ -280,6 +294,28 @@[m [mdef get_user_from_token(request):[m
         return None[m
 [m
 [m
[32m+[m[32mdef set_auth_cookie(response, token):[m
[32m+[m[32m    response.set_cookie([m
[32m+[m[32m        settings.AUTH_COOKIE_NAME,[m
[32m+[m[32m        token,[m
[32m+[m[32m        max_age=settings.AUTH_COOKIE_MAX_AGE,[m
[32m+[m[32m        httponly=True,[m
[32m+[m[32m        secure=settings.AUTH_COOKIE_SECURE,[m
[32m+[m[32m        samesite=settings.AUTH_COOKIE_SAMESITE,[m
[32m+[m[32m        path='/',[m
[32m+[m[32m    )[m
[32m+[m[32m    return response[m
[32m+[m
[32m+[m
[32m+[m[32mdef clear_auth_cookie(response):[m
[32m+[m[32m    response.delete_cookie([m
[32m+[m[32m        settings.AUTH_COOKIE_NAME,[m
[32m+[m[32m        path='/',[m
[32m+[m[32m        samesite=settings.AUTH_COOKIE_SAMESITE,[m
[32m+[m[32m    )[m
[32m+[m[32m    return response[m
[32m+[m
[32m+[m
 # ===================== AUTH API =====================[m
 [m
 @api_view(['GET'])[m
[36m@@ -404,10 +440,10 @@[m [mdef auth_register(request):[m
         is_trusted=False  # OTP tasdiqlanguncha False[m
     )[m
 [m
[31m-    return Response({[m
[31m-        'token': session.token,[m
[31m-        'user': CRMUserSerializer(user).data[m
[31m-    })[m
[32m+[m[32m    response = Response({'user': CRMUserSerializer(user).data})[m
[32m+[m[32m    # Token endi javob tanasida YO'Q — faqat httpOnly cookie orqali yuboriladi,[m
[32m+[m[32m    # shuning uchun frontend uni umuman ko'rmaydi/saqlamaydi (XSS himoyasi).[m
[32m+[m[32m    return set_auth_cookie(response, session.token)[m
 [m
 [m
 @api_view(['POST'])[m
[36m@@ -455,11 +491,11 @@[m [mdef auth_login(request):[m
         daemon=True,[m
     ).start()[m
 [m
[31m-    return Response({[m
[31m-        'token': session.token,[m
[32m+[m[32m    response = Response({[m
         'is_trusted': is_trusted,[m
         'user': CRMUserSerializer(user).data[m
     })[m
[32m+[m[32m    return set_auth_cookie(response, session.token)[m
 [m
 [m
 @api_view(['POST'])[m
[36m@@ -470,7 +506,7 @@[m [mdef auth_trust_device(request):[m
         return Response({'error': "Token noto'g'ri"}, status=401)[m
 [m
     device_id = request.data.get('device_id', '')[m
[31m-    token = request.headers.get('Authorization', '').replace('Bearer ', '')[m
[32m+[m[32m    token = get_session_token(request)[m
 [m
     # Joriy sessionni ishonchli qilish[m
     CRMSession.objects.filter(token=token).update(is_trusted=True)[m
[36m@@ -485,7 +521,7 @@[m 