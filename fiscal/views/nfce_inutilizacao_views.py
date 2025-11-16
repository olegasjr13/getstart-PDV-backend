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

from fiscal.serializers_inutilizacao import (
    InutilizarFaixaNfceInputSerializer,
    InutilizarFaixaNfceOutputSerializer,
)
from fiscal.services.inutilizacao_service import inutilizar_faixa_nfce

logger = logging.getLogger("pdv.fiscal")
root_logger = logging.getLogger()


def _tenant_id_from_request(request):
    return getattr(getattr(request, "tenant", None), "schema_name", None)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def inutilizar_faixa_nfce_view(request):
    """
    Endpoint HTTP para inutilização de faixa numérica de NFC-e.

    URL final:
        POST /api/v1/fiscal/nfce/inutilizar/
    """

    tenant_id = _tenant_id_from_request(request)
    user = request.user

    try:
        ser_in = InutilizarFaixaNfceInputSerializer(data=request.data)
        ser_in.is_valid(raise_exception=True)

        data = ser_in.validated_data

        result = inutilizar_faixa_nfce(
            user=user,
            filial_id=str(data["filial_id"]),
            serie=data["serie"],
            numero_inicial=data["numero_inicial"],
            numero_final=data["numero_final"],
            motivo=data["motivo"],
            request_id=data["request_id"],
        )

        ser_out = InutilizarFaixaNfceOutputSerializer(
            {
                "request_id": result.request_id,
                "filial_id": result.filial_id,
                "serie": result.serie,
                "numero_inicial": result.numero_inicial,
                "numero_final": result.numero_final,
                "protocolo": result.protocolo,
                "status": result.status,
                "mensagem": result.mensagem,
            }
        )

        extra = {
            "event": "nfce_inutilizar",
            "tenant_id": tenant_id,
            "user_id": getattr(user, "id", None),
            "filial_id": result.filial_id,
            "serie": result.serie,
            "numero_inicial": result.numero_inicial,
            "numero_final": result.numero_final,
            "status": result.status,
            "outcome": "success",
        }
        logger.info("nfce_inutilizar", extra=extra)
        root_logger.info("nfce_inutilizar", extra=extra)

        return Response(ser_out.data, status=status.HTTP_200_OK)

    except DRFValidationError as exc:
        logger.warning(
            "nfce_inutilizar_validacao",
            extra={
                "event": "nfce_inutilizar",
                "tenant_id": tenant_id,
                "user_id": getattr(user, "id", None),
                "errors": exc.detail,
                "outcome": "validation_error",
            },
        )
        raise

    except DjangoValidationError as exc:
        logger.warning(
            "nfce_inutilizar_validacao_django",
            extra={
                "event": "nfce_inutilizar",
                "tenant_id": tenant_id,
                "user_id": getattr(user, "id", None),
                "errors": exc.message_dict if hasattr(exc, "message_dict") else exc.messages,
                "outcome": "validation_error",
            },
        )
        raise DRFValidationError(detail=exc.message_dict)

    except NotFound as exc:
        logger.warning(
            "nfce_inutilizar_not_found",
            extra={
                "event": "nfce_inutilizar",
                "tenant_id": tenant_id,
                "user_id": getattr(user, "id", None),
                "detail": str(exc.detail),
                "outcome": "not_found",
            },
        )
        raise

    except PermissionDenied as exc:
        logger.warning(
            "nfce_inutilizar_permission_denied",
            extra={
                "event": "nfce_inutilizar",
                "tenant_id": tenant_id,
                "user_id": getattr(user, "id", None),
                "detail": str(exc.detail),
                "outcome": "forbidden",
            },
        )
        raise

    except APIException as exc:
        logger.error(
            "nfce_inutilizar_api_exception",
            extra={
                "event": "nfce_inutilizar",
                "tenant_id": tenant_id,
                "user_id": getattr(user, "id", None),
                "detail": str(exc.detail),
                "outcome": "api_exception",
            },
        )
        raise

    except Exception as exc:
        logger.exception(
            "nfce_inutilizar_erro",
            extra={
                "event": "nfce_inutilizar",
                "tenant_id": tenant_id,
                "user_id": getattr(user, "id", None),
                "error": str(exc),
            },
        )
        root_logger.exception(
            "nfce_inutilizar_erro",
            extra={
                "event": "nfce_inutilizar",
                "tenant_id": tenant_id,
                "user_id": getattr(user, "id", None),
                "error": str(exc),
            },
        )

        raise APIException(
            detail={
                "code": "FISCAL_5999",
                "message": "Erro ao comunicar com a SEFAZ para inutilização.",
            }
        )
