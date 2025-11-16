# fiscal/views/nfce_cancelamento_views.py

import logging

from django.core.exceptions import ValidationError as DjangoValidationError

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import (
    APIException,
    ValidationError as DRFValidationError,
    NotFound,
    PermissionDenied,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from fiscal.serializers_cancelamento import (
    CancelarNfceInputSerializer,
    CancelarNfceOutputSerializer,
)
from fiscal.services.cancelamento_service import cancelar_nfce

logger = logging.getLogger("pdv.fiscal")
root_logger = logging.getLogger()


def _tenant_id_from_request(request):
    return getattr(getattr(request, "tenant", None), "schema_name", None)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def cancelar_nfce_view(request):
    """
    Endpoint HTTP para cancelamento de NFC-e.

    URL final:
        POST /api/v1/fiscal/nfce/cancelar/

    Fluxo:
      1) Valida payload com CancelarNfceInputSerializer.
      2) Chama service fiscal.services.cancelamento_service.cancelar_nfce.
      3) Retorna CancelarNfceOutputSerializer.
      4) Aplica tratamento de erros alinhado ao resto do módulo fiscal.
    """

    tenant_id = _tenant_id_from_request(request)
    user = request.user

    try:
        ser_in = CancelarNfceInputSerializer(data=request.data)
        ser_in.is_valid(raise_exception=True)

        data = ser_in.validated_data

        result = cancelar_nfce(
            user=user,
            chave_acesso=data.get("chave_acesso"),
            filial_id=str(data["filial_id"]) if data.get("filial_id") else None,
            numero=data.get("numero"),
            serie=data.get("serie"),
            motivo=data["motivo"],
        )

        ser_out = CancelarNfceOutputSerializer(
            {
                "request_id": result.request_id,
                "filial_id": result.filial_id,
                "terminal_id": result.terminal_id,
                "numero": result.numero,
                "serie": result.serie,
                "chave_acesso": result.chave_acesso,
                "protocolo": result.protocolo,
                "status": result.status,
                "mensagem": result.mensagem,
            }
        )

        extra = {
            "event": "nfce_cancelar",
            "tenant_id": tenant_id,
            "user_id": getattr(user, "id", None),
            "filial_id": result.filial_id,
            "terminal_id": result.terminal_id,
            "chave_acesso": result.chave_acesso,
            "numero": result.numero,
            "serie": result.serie,
            "status": result.status,
            "outcome": "success",
        }
        logger.info("nfce_cancelar", extra=extra)
        root_logger.info("nfce_cancelar", extra=extra)

        return Response(ser_out.data, status=status.HTTP_200_OK)

    except DRFValidationError as exc:
        logger.warning(
            "nfce_cancelar_validacao",
            extra={
                "event": "nfce_cancelar",
                "tenant_id": tenant_id,
                "user_id": getattr(user, "id", None),
                "errors": exc.detail,
                "outcome": "validation_error",
            },
        )
        raise

    except DjangoValidationError as exc:
        logger.warning(
            "nfce_cancelar_validacao_django",
            extra={
                "event": "nfce_cancelar",
                "tenant_id": tenant_id,
                "user_id": getattr(user, "id", None),
                "errors": exc.message_dict if hasattr(exc, "message_dict") else exc.messages,
                "outcome": "validation_error",
            },
        )
        raise DRFValidationError(detail=exc.message_dict)

    except NotFound as exc:
        logger.warning(
            "nfce_cancelar_not_found",
            extra={
                "event": "nfce_cancelar",
                "tenant_id": tenant_id,
                "user_id": getattr(user, "id", None),
                "detail": str(exc.detail),
                "outcome": "not_found",
            },
        )
        raise

    except PermissionDenied as exc:
        logger.warning(
            "nfce_cancelar_permission_denied",
            extra={
                "event": "nfce_cancelar",
                "tenant_id": tenant_id,
                "user_id": getattr(user, "id", None),
                "detail": str(exc.detail),
                "outcome": "forbidden",
            },
        )
        raise

    except APIException as exc:
        logger.error(
            "nfce_cancelar_api_exception",
            extra={
                "event": "nfce_cancelar",
                "tenant_id": tenant_id,
                "user_id": getattr(user, "id", None),
                "detail": str(exc.detail),
                "outcome": "api_exception",
            },
        )
        raise

    except Exception as exc:
        logger.exception(
            "nfce_cancelar_erro",
            extra={
                "event": "nfce_cancelar",
                "tenant_id": tenant_id,
                "user_id": getattr(user, "id", None),
                "error": str(exc),
            },
        )
        root_logger.exception(
            "nfce_cancelar_erro",
            extra={
                "event": "nfce_cancelar",
                "tenant_id": tenant_id,
                "user_id": getattr(user, "id", None),
                "error": str(exc),
            },
        )

        raise APIException(
            detail={
                "code": "FISCAL_5999",
                "message": "Erro ao comunicar com a SEFAZ para cancelamento.",
            }
        )
