from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle

from fiscal.serializers import ReservarNumeroInputSerializer
from fiscal.services.numero_service import reservar_numero_nfce
from ..serializers import ReservaNumeracaoResponse


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([UserRateThrottle])
def reservar_numeracao(request, id):
    """
    [DEPRECATED] Endpoint LEGADO de reserva de numeração de NFC-e.

    🔹 Mantido apenas para compatibilidade.
    🔹 Agora delega para o fluxo oficial:
        - fiscal.services.numero_service.reservar_numero_nfce
        - fiscal.views.nfce_views.reservar_numero

    ✅ Nova regra deste endpoint:
      - Continua recebendo o terminal via URL: /terminais/<uuid:id>/reservar-numeracao
      - Precisa receber no body:
            {
                "serie": <int>,
                "request_id": "<uuid-v4>"
            }

      - Usa o mesmo service robusto do app fiscal:
            - Valida vínculo usuário ↔ filial do terminal
            - Valida certificado A1 (não expirado)
            - Garante idempotência por request_id
            - Garante numeração sequencial sem buracos

    🔁 Resposta:
      - Mantém o formato ENXUTO legado:
            {
                "numero": <int>,
                "serie": <int>
            }
        (Ou seja, não expõe terminal_id, filial_id, request_id aqui)
    """

    # Monta o payload no formato esperado pelo fluxo oficial
    payload = {
        "terminal_id": id,
        "serie": request.data.get("serie"),
        "request_id": request.data.get("request_id"),
    }

    # Reaproveita o mesmo serializer de entrada do app fiscal
    ser_in = ReservarNumeroInputSerializer(data=payload)
    ser_in.is_valid(raise_exception=True)

    result = reservar_numero_nfce(
        user=request.user,
        terminal_id=ser_in.validated_data["terminal_id"],
        serie=ser_in.validated_data["serie"],
        request_id=ser_in.validated_data["request_id"],
    )

    # Mantém o contrato legado: só número e série
    legacy_payload = {
        "numero": result.numero,
        "serie": result.serie,
    }
    ser_out = ReservaNumeracaoResponse(legacy_payload)

    return Response(ser_out.data, status=200)
