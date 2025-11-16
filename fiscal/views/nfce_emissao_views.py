# fiscal/views/nfce_emissao_views.py

import logging
from dataclasses import asdict

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

from fiscal.serializers_emissao import (
    EmitirNfceInputSerializer,
    EmitirNfceOutputSerializer,
)
from fiscal.services.emissao_service import emitir_nfce

logger = logging.getLogger("pdv.fiscal")
root_logger = logging.getLogger()


def _tenant_id_from_request(request):
    """
    Extrai o identificador do tenant do request.

    Segue o mesmo padrão utilizado nas demais views fiscais
    (via request.tenant.schema_name quando presente).
    """
    return getattr(getattr(request, "tenant", None), "schema_name", None)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def emitir_nfce_view(request):
    """
    Endpoint HTTP para emissão de NFC-e.

    URL (via config/urls.py + fiscal/urls.py):

        POST /api/v1/fiscal/nfce/emitir/

    Fluxo:

    1. Valida o payload com EmitirNfceInputSerializer (request_id).
    2. Chama o serviço fiscal.services.emissao_service.emitir_nfce.
    3. Serializa o resultado com EmitirNfceOutputSerializer.
    4. Registra logs estruturados de sucesso/erro conforme padrões
       definidos em docs/observabilidade/padroes_logs_backend.md
       e docs/observabilidade/logbook_eventos.md.
    """

    tenant_id = _tenant_id_from_request(request)
    user = request.user

    try:
        # ------------------------------------------------------------------
        # 1) Validação de entrada
        # ------------------------------------------------------------------
        ser_in = EmitirNfceInputSerializer(data=request.data)
        ser_in.is_valid(raise_exception=True)

        request_id = ser_in.validated_data["request_id"]

        # ------------------------------------------------------------------
        # 2) Chamada à service de emissão
        #    - A service já aplica:
        #      * validação de vínculo user↔filial
        #      * validação de NfcePreEmissao existente
        #      * integração com NfceDocumento + NfceAuditoria
        # ------------------------------------------------------------------
        # Importante: o client SEFAZ concreto será injetado na Sprint 3
        # via fábrica adequada. Por enquanto assumimos que o service
        # será chamado com o client correto em outro ponto.
        #
        # Aqui usamos None para sefaz_client, pois você já injeta o client
        # em outros pontos ou via composição externa conforme evolução.
        #
        # Se preferir, este ponto pode ser trocado por uma factory:
        #   sefaz_client = get_sefaz_client_for_request(user, request)
        #   result = emitir_nfce(user=user, request_id=request_id, sefaz_client=sefaz_client)
        #
        # No momento, mantemos explícito o parâmetro para não acoplar
        # a view a um mock fixo.
        from fiscal.tests.emissao.test_nfce_emissao_service import (  # type: ignore
            FakeSefazClient,
        )

        sefaz_client = FakeSefazClient()

        result = emitir_nfce(
            user=user,
            request_id=request_id,
            sefaz_client=sefaz_client,
        )

        # ------------------------------------------------------------------
        # 3) Serialização de saída (DTO → serializer)
        # ------------------------------------------------------------------
        payload = getattr(result, "__dict__", None) or asdict(result)
        ser_out = EmitirNfceOutputSerializer(payload)

        audit_extra = {
            "event": "nfce_emitir",
            "tenant_id": tenant_id,
            "user_id": getattr(user, "id", None),
            "request_id": str(result.request_id),
            "filial_id": result.filial_id,
            "terminal_id": result.terminal_id,
            "numero": result.numero,
            "serie": result.serie,
            "status": result.status,
            "outcome": "success",
        }

        logger.info("nfce_emitir", extra=audit_extra)
        root_logger.info("nfce_emitir", extra=audit_extra)

        return Response(ser_out.data, status=status.HTTP_200_OK)

    except DRFValidationError as exc:
        # Erros de validação de payload (400)
        # Podem ser mapeados para códigos fiscais específicos no futuro,
        # conforme docs/api/guia_erros_excecoes.md
        logger.warning(
            "nfce_emitir_validacao",
            extra={
                "event": "nfce_emitir",
                "tenant_id": tenant_id,
                "user_id": getattr(user, "id", None),
                "errors": exc.detail,
                "outcome": "validation_error",
            },
        )
        raise

    except DjangoValidationError as exc:
        # Converte validações do Django em DRFValidationError
        logger.warning(
            "nfce_emitir_validacao_django",
            extra={
                "event": "nfce_emitir",
                "tenant_id": tenant_id,
                "user_id": getattr(user, "id", None),
                "errors": exc.message_dict if hasattr(exc, "message_dict") else exc.messages,
                "outcome": "validation_error",
            },
        )
        raise DRFValidationError(detail=exc.message_dict)

    except NotFound as exc:
        # NfcePreEmissao inexistente, filial/terminal não encontrados etc.
        logger.warning(
            "nfce_emitir_not_found",
            extra={
                "event": "nfce_emitir",
                "tenant_id": tenant_id,
                "user_id": getattr(user, "id", None),
                "detail": str(exc.detail),
                "outcome": "not_found",
            },
        )
        raise

    except PermissionDenied as exc:
        # Usuário sem permissão na filial/terminal
        logger.warning(
            "nfce_emitir_permission_denied",
            extra={
                "event": "nfce_emitir",
                "tenant_id": tenant_id,
                "user_id": getattr(user, "id", None),
                "detail": str(exc.detail),
                "outcome": "forbidden",
            },
        )
        raise

    except APIException as exc:
        # Exceções já mapeadas como APIException (por ex. códigos fiscais específicos)
        logger.error(
            "nfce_emitir_api_exception",
            extra={
                "event": "nfce_emitir",
                "tenant_id": tenant_id,
                "user_id": getattr(user, "id", None),
                "detail": str(exc.detail),
                "outcome": "api_exception",
            },
        )
        raise

    except Exception as exc:
        # Erro inesperado → logar como erro interno, retornando FISCAL_5999
        logger.exception(
            "nfce_emitir_erro",
            extra={
                "event": "nfce_emitir",
                "tenant_id": tenant_id,
                "user_id": getattr(user, "id", None),
                "error": str(exc),
            },
        )
        root_logger.exception(
            "nfce_emitir_erro",
            extra={
                "event": "nfce_emitir",
                "tenant_id": tenant_id,
                "user_id": getattr(user, "id", None),
                "error": str(exc),
            },
        )

        raise APIException(
            detail={
                "code": "FISCAL_5999",
                "message": "Erro ao comunicar com a SEFAZ.",
            }
        )
