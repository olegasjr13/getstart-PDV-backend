from rest_framework.decorators import api_view, throttle_classes
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken

from django.utils import timezone
from datetime import timedelta
from django.conf import settings
from filial.models import Filial
from terminal.models import Terminal
from django.contrib.auth import get_user_model
import hashlib

from usuario.serializers import LoginSerializer, PinSerializer

User = get_user_model()

def _hash_pin(pin:str)->str:
    return hashlib.pbkdf2_hmac("sha256", pin.encode(), b"gs-pdv", 260000).hex()

@api_view(["POST"])
def login(request):
    ser = LoginSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    data = ser.validated_data
    user = authenticate(username=data["username"], password=data["password"])
    if not user:
        return Response({"code":"AUTH_1001","message":"Credenciais inválidas"}, status=401)

    # validar terminal e vínculo com filial
    try:
        term = Terminal.objects.get(id=data["terminal_id"])
    except Terminal.DoesNotExist:
        return Response({"code":"AUTH_1005","message":"Terminal inválido"}, status=403)

    # Checagem: usuário possui acesso à filial do terminal?
    # Como Filial é multi-tenant, aqui assumimos filial_id armazenado no terminal
    has_access = user.userfilial_set.filter(filial_id=term.filial_id).exists()
    if not has_access:
        return Response({"code":"AUTH_1006","message":"Usuário não autorizado na filial do terminal"}, status=403)

    refresh = RefreshToken.for_user(user)
    # claims
    refresh["perfil"] = user.perfil
    refresh["terminal_id"] = str(term.id)
    refresh["filial_id"] = str(term.filial_id)

    access = refresh.access_token
    # inatividade (>2h) — guardaremos last_activity em cache/db (fase 2)
    # por enquanto, incluímos claim de emissão
    access["iat_server"] = int(timezone.now().timestamp())

    return Response({
        "access": str(access),
        "refresh": str(refresh),
        "perfil": user.perfil,
        "terminal_id": str(term.id),
        "filial_id": str(term.filial_id),
    })

@api_view(["POST"])
@throttle_classes([])  # usar throttle de "login" configurado no DRF se desejar
def refresh(request):
    from rest_framework_simplejwt.serializers import TokenRefreshSerializer
    ser = TokenRefreshSerializer(data=request.data)
    if not ser.is_valid():
        return Response({"code":"AUTH_1011","message":"Refresh token inválido ou expirado."}, status=401)
    return Response(ser.validated_data)

@api_view(["POST"])
def validar_pin(request):
    ser = PinSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    data = ser.validated_data
    try:
        user = User.objects.get(id=data["user_id"])
    except User.DoesNotExist:
        return Response({"code":"AUTH_1002","message":"Usuário inexistente"}, status=404)

    if not user.pin_hash:
        return Response({"code":"AUTH_1008","message":"PIN não cadastrado"}, status=400)

    if _hash_pin(data["pin"]) != user.pin_hash:
        return Response({"code":"PDV_6004","message":"PIN inválido"}, status=403)

    return Response({"ok": True})
