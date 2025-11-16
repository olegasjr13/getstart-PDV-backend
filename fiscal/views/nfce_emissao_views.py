# fiscal/views/nfce_emissao_views.py

import logging
from dataclasses import asdict

from django.core.exceptions import ValidationError as DjangoValidationError, ObjectDoesNotExist

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

from filial.models.filial_models import Filial
from fiscal.serializers_emissao import (
    EmitirNfceInputSerializer,
    EmitirNfceOutputSerializer,
)
from fiscal.services.emissao_service import emitir_nfce
from fiscal.models import NfcePreEmissao
from fiscal.sefaz_factory import get_sefaz_client_for_filial

logger = logging.getLogger("pdv.fiscal")
root_logger = logging.getLogger()


class SefazEmitirAdapter:
    """
    Adaptador que expõe o método emitir_nfce(pre_emissao=...)
    a partir de um client baseado em SefazClientProtocol (MockSefazClient, etc).

    A service emitir_nfce continua falando com um client que tem emitir_nfce,
    mas por baixo usamos autorizar_nfce(filial, pre_emissao, numero, serie)
    da implementação real (MockSefazClient ou futura implementação por UF).
    """

    def __init__(self, inner_client, filial: Filial):
        self.inner_client = inner_client
        self.filial = filial

    def emitir_nfce(self, *, pre_emissao):
        """
        Adapta a chamada do client SEFAZ real (autorizar_nfce) para o formato
        de dicionário que a service emitir_nfce espera hoje.
        """
        resp = self.inner_client.autorizar_nfce(
            filial=self.filial,
            pre_emissao=pre_emissao,
            numero=pre_emissao.numero,
            serie=pre_emissao.serie,
        )

        status = "autorizada" if resp.codigo == 100 else "rejeitada"

        return {
            "chave_acesso": resp.chave_acesso,
            "protocolo": resp.protocolo,
            "status": status,
            "xml_autorizado": resp.xml_autorizado,
            "mensagem": resp.mensagem,
            "raw": resp.raw,
        }


def _tenant_id_from_request(request):
    """
    Extrai o identificador do tenant do request.
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
    2. Localiza a NfcePreEmissao e a filial correspondente.
    3. Usa a factory get_sefaz_client_for_filial para obter o client SEFAZ.
    4. Adapta o client para o contrato da service (emitir_nfce).
    5. Chama o serviço fiscal.services.emissao_service.emitir_nfce.
    6. Serializa o resultado com EmitirNfceOutputSerializer.
    7. Registra logs estruturados de sucesso/erro.
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
        # 2) Localiza pré-emissão e filial
        # ------------------------------------------------------------------
        try:
            pre = NfcePreEmissao.objects.get(request_id=request_id)
        except ObjectDoesNotExist:
            raise NotFound(
                detail="Pré-emissão NFC-e não encontrada para o request_id informado."
            )

        try:
            filial = Filial.objects.get(id=pre.filial_id)
        except Filial.DoesNotExist:
            raise NotFound(detail="Filial associada à pré-emissão não encontrada.")

        # ------------------------------------------------------------------
        # 3) Obtém client SEFAZ via factory (SP/MG/RJ/ES, homolog/produção)
        # ------------------------------------------------------------------
        inner_client = get_sefaz_client_for_filial(filial)

        # ------------------------------------------------------------------
        # 4) Adaptador que expõe emitir_nfce(pre_emissao=...)
        # ------------------------------------------------------------------
        sefaz_client = SefazEmitirAdapter(inner_client, filial)

        # ------------------------------------------------------------------
        # 5) Chamada à service de emissão
        # ------------------------------------------------------------------
        result = emitir_nfce(
            user=user,
            request_id=request_id,
            sefaz_client=sefaz_client,
        )

        # ------------------------------------------------------------------
        # 6) Serialização de saída
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
