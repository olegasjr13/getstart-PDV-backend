from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db import transaction, connection
from filial.models.filial_models import Filial
from ..models.terminal_models import Terminal
from ..serializers import ReservaNumeracaoResponse
from django.utils import timezone

def a1_expirado(filial: Filial)->bool:
    return (filial.a1_expires_at and filial.a1_expires_at <= timezone.now())

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def reservar_numeracao(request, id):
    # Idempotency-Key (opcional aqui; na pré-emissão será obrigatório)
    idem = request.headers.get("Idempotency-Key")

    try:
        term = Terminal.objects.select_for_update().get(id=id)
    except Terminal.DoesNotExist:
        return Response({"code":"PDV_6006","message":"Terminal não encontrado"}, status=404)

    try:
        filial = Filial.objects.get(id=term.filial_id)
    except Filial.DoesNotExist:
        return Response({"code":"PDV_6008","message":"Filial não encontrada"}, status=404)

    if a1_expirado(filial):
        return Response({"code":"FISCAL_4005","message":"Certificado A1 expirado"}, status=403)

    with transaction.atomic():
        term = Terminal.objects.select_for_update().get(id=id)
        term.numero_atual += 1
        term.save(update_fields=["numero_atual"])
        data = {"numero": term.numero_atual, "serie": term.serie}
    return Response(ReservaNumeracaoResponse(data).data, status=200)
