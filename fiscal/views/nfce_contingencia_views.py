# fiscal/views/nfce_contingencia_views.py
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

from fiscal.models import NfceDocumento
from fiscal.services.contingencia_service import regularizar_contingencia_nfce
from fiscal.sefaz_factory import get_sefaz_client_for_filial

logger = logging.getLogger("pdv.fiscal")
root_logger = logging.getLogger()


def _tenant_id_from_request(request):
    """
    Extrai o identificador do tenant do request, para logging estruturado.
    """
    tenant = getattr(request, "tenant", None)
    return getattr(tenant, "schema_name", None) or getattr(tenant, "id", None)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def nfce_regularizar_contingencia_view(request):
    """
    POST /api/v1/fiscal/nfce/regularizar-contingencia/

    Corpo esperado:
      {
        "documento_id": "<uuid do NfceDocumento em contingência>"
      }

    Resposta de sucesso (200):
      {
        "code": "FISCAL_0000",
        "message": "Regularização de contingência processada com sucesso.",
        "data": {
            ... DTO retornado por regularizar_contingencia_nfce ...
        }
      }
    """
    user = request.user
    tenant_id = _tenant_id_from_request(request)

    # ----------------------------------------------------------------------
    # 0) Garantia extra de autenticação (além de IsAuthenticated do DRF)
    # ----------------------------------------------------------------------
    if not user or not user.is_authenticated:
        # Isso cobre o caso dos testes que chamam a API sem JWT
        logger.warning(
            "nfce_regularizar_contingencia_sem_autenticacao",
            extra={
                "event": "nfce_regularizar_contingencia",
                "tenant_id": tenant_id,
            },
        )
        raise PermissionDenied("Credenciais de autenticação inválidas ou ausentes.")

    try:
        # ------------------------------------------------------------------
        # 1) Validação básica do payload
        # ------------------------------------------------------------------
        payload = request.data or {}
        documento_id = payload.get("documento_id")

        if not documento_id:
            raise DRFValidationError({"documento_id": ["Este campo é obrigatório."]})

        # ------------------------------------------------------------------
        # 2) Carrega o documento para descobrir a filial -> factory de SEFAZ
        # ------------------------------------------------------------------
        try:
            doc = (
                NfceDocumento.objects.select_related("filial")
                .only("id", "filial_id", "filial__uf", "filial__ambiente")
                .get(id=documento_id)
            )
        except NfceDocumento.DoesNotExist as exc:
            logger.warning(
                "nfce_regularizar_contingencia_documento_nao_encontrado",
                extra={
                    "event": "nfce_regularizar_contingencia",
                    "tenant_id": tenant_id,
                    "user_id": getattr(user, "id", None),
                    "documento_id": str(documento_id),
                    "error": str(exc),
                },
            )
            # 404 semântica – os testes aceitam 400 ou 404
            raise NotFound(
                detail={
                    "code": "FISCAL_4004",
                    "message": "Documento não encontrado para regularização de contingência.",
                }
            )

        filial = doc.filial

        # ------------------------------------------------------------------
        # 3) Obtém client SEFAZ via factory (SP/MG/RJ/ES, homolog/produção)
        # ------------------------------------------------------------------
        sefaz_client = get_sefaz_client_for_filial(filial)

        # ------------------------------------------------------------------
        # 4) Chama a service de domínio
        # ------------------------------------------------------------------
        result = regularizar_contingencia_nfce(
            user=user,
            documento_id=str(doc.id),
            sefaz_client=sefaz_client,
        )

        response_body = {
            "code": "FISCAL_0000",
            "message": "Regularização de contingência processada com sucesso.",
            "data": asdict(result),
        }

        logger.info(
            "nfce_regularizar_contingencia_sucesso",
            extra={
                "event": "nfce_regularizar_contingencia",
                "tenant_id": tenant_id,
                "user_id": getattr(user, "id", None),
                "documento_id": str(doc.id),
                "status_antes": result.status_antes,
                "status_depois": result.status_depois,
                "em_contingencia_antes": result.em_contingencia_antes,
                "em_contingencia_depois": result.em_contingencia_depois,
                "regularizada": result.regularizada,
            },
        )

        return Response(response_body, status=status.HTTP_200_OK)

    except (DRFValidationError, DjangoValidationError) as exc:
        # Erros de validação -> 400
        logger.warning(
            "nfce_regularizar_contingencia_validacao_erro",
            extra={
                "event": "nfce_regularizar_contingencia",
                "tenant_id": tenant_id,
                "user_id": getattr(user, "id", None),
                "error": str(exc),
            },
        )
        raise

    except PermissionDenied:
        # Deixa o DRF converter em 403
        logger.warning(
            "nfce_regularizar_contingencia_permissao_negada",
            extra={
                "event": "nfce_regularizar_contingencia",
                "tenant_id": tenant_id,
                "user_id": getattr(user, "id", None),
            },
        )
        raise

    except (NotFound, ObjectDoesNotExist) as exc:
        # Normaliza "não encontrado" para 404 com payload fiscal
        logger.warning(
            "nfce_regularizar_contingencia_nao_encontrado",
            extra={
                "event": "nfce_regularizar_contingencia",
                "tenant_id": tenant_id,
                "user_id": getattr(user, "id", None),
                "error": str(exc),
            },
        )
        raise NotFound(
            detail={
                "code": "FISCAL_4004",
                "message": "Documento não encontrado para regularização de contingência.",
            }
        )

    except APIException:
        # Deixa passar APIException já estruturada (por exemplo FISCAL_5999 da service)
        logger.error(
            "nfce_regularizar_contingencia_api_exception",
            extra={
                "event": "nfce_regularizar_contingencia",
                "tenant_id": tenant_id,
                "user_id": getattr(user, "id", None),
            },
        )
        raise

    except Exception as exc:
        # Falha inesperada -> erro genérico padronizado
        logger.exception(
            "nfce_regularizar_contingencia_erro_inesperado",
            extra={
                "event": "nfce_regularizar_contingencia",
                "tenant_id": tenant_id,
                "user_id": getattr(user, "id", None),
                "error": str(exc),
            },
        )
        raise APIException(
            detail={
                "code": "FISCAL_5999",
                "message": "Erro ao comunicar com a SEFAZ para regularização de contingência.",
            }
        )
