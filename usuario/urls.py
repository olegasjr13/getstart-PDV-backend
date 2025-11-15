from django.urls import path
from .views.usuario_views import login, refresh, validar_pin

urlpatterns = [
    path("auth/login", login),
    path("auth/refresh", refresh),
    path("auth/validar-pin", validar_pin),
]
