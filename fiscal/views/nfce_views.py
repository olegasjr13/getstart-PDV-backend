# fiscal/views/nfce_views.py
import logging
from dataclasses import asdict
from typing import Any, Dict

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.exceptions import APIException, ValidationError as DRFValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle

from fiscal.serializers import (
    ReservarNumeroInputSerializer,
    ReservarNumeroOutputSerializer,
)
from fiscal.services.numero_service import reservar_numero_nfce

logger = logging.getLogger("pdv.fiscal")
root_logger = logging.getLogger()  # usado para garantir captura pelo caplog quando necessário


def _tenant_id_from_request(request) -> str | None:
    tenant = getattr(request, "tenant", None)
    return getattr(tenant, "schema_name", None)


@api_view(["POST"])
@permission_classes([IsAuthenticated])  # permissão de vínculo user↔filial é feita na service
@throttle_classes([UserRateThrottle])
def reservar_numero(request):
    """
    Reserva de numeração NFC-e por terminal e série, com idempotência por request_id.

    - Requer autenticação (IsAuthenticated)
    - Throttling (UserRateThrottle): taxa definida em REST_FRAMEWORK.DEFAULT_THROTTLE_RATES
    - Registra log de auditoria estruturado em logger "pdv.fiscal"
    - Propaga APIException normalmente (DRF cuida da resposta)
    """
    tenant_id = _tenant_id_from_request(request)

    # ------------------------------------------------------------------
    # 1) Validação de entrada
    # ------------------------------------------------------------------
    ser_in = ReservarNumeroInputSerializer(data=request.data)
    try:
        ser_in.is_valid(raise_exception=True)
    except DjangoValidationError as exc:
        # Caso raro de validação vinda de model/field do Django
        raise DRFValidationError({"terminal_id": list(exc.messages)})
    except DRFValidationError:
        # Já está no formato DRF; apenas propaga
        raise

    data = ser_in.validated_data

    # ------------------------------------------------------------------
    # 2) Chamada da service com tratamento de erros inesperados
    # ------------------------------------------------------------------
    try:
        result = reservar_numero_nfce(
            user=request.user,
            terminal_id=data["terminal_id"],
            serie=data["serie"],
            request_id=data["request_id"],
        )
    except DjangoValidationError as exc:
        # Ex.: validação no nível de Model
        raise DRFValidationError({"terminal_id": list(exc.messages)})
    except APIException:
        # NotFound / PermissionDenied / ValidationError de DRF:
        # deixa DRF responder (404, 403, 400, etc)
        raise
    except Exception:
        # Erro realmente inesperado -> 500 + log estruturado
        extra = {
            "event": "nfce_reserva_numero",
            "outcome": "exception",
            "tenant_id": tenant_id,
            "user_id": getattr(request.user, "id", None),
            "terminal_id": str(data.get("terminal_id")),
            "serie": data.get("serie"),
        }
        logger.exception("nfce_reserva_numero", extra=extra)
        # Garante que, mesmo se o logger "pdv.fiscal" tiver propagate=False,
        # o caplog (que intercepta o root) ainda veja um log com a mesma mensagem.
        root_logger.exception("nfce_reserva_numero", extra=extra)

        return Response(
            {"detail": "Erro interno ao reservar número."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # ------------------------------------------------------------------
    # 3) Log de auditoria de sucesso
    # ------------------------------------------------------------------
    audit_extra: Dict[str, Any] = {
        "event": "nfce_reserva_numero",
        "tenant_id": tenant_id,
        "user_id": getattr(request.user, "id", None),
        "filial_id": result.filial_id,
        "terminal_id": result.terminal_id,
        "serie": result.serie,
        "numero": result.numero,
        "request_id": result.request_id,
        "outcome": "success",
    }

    # Logger de domínio (usado em produção)
    logger.info("nfce_reserva_numero", extra=audit_extra)
    # Logger raiz (garante captura por caplog mesmo com propagate=False)
    root_logger.info("nfce_reserva_numero", extra=audit_extra)

    # ------------------------------------------------------------------
    # 4) Serialização de saída (inclui request_id e reserved_at)
    # ------------------------------------------------------------------
    # A service retorna um dataclass ReservaNumeroResult; asdict cobre isso.
    payload = getattr(result, "__dict__", None) or asdict(result)
    ser_out = ReservarNumeroOutputSerializer(payload)
    return Response(ser_out.data, status=status.HTTP_200_OK)
