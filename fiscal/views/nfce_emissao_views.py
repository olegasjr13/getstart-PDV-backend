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

from fiscal.models import NfcePreEmissao
from fiscal.sefaz_factory import get_sefaz_client_for_filial
from fiscal.services.emissao_service import emitir_nfce, _build_result_from_document
from fiscal.models import NfcePreEmissao, NfceDocumento


logger = logging.getLogger("pdv.fiscal")
root_logger = logging.getLogger()

def _result_to_dict(result):
        """
        Converte o result da emissão NFC-e em dict de forma segura.
        Suporta:
            - dataclass
            - dict
            - objetos comuns (usar __dict__)
            - outros (fallback para string)
        """
        from dataclasses import is_dataclass, asdict

        if is_dataclass(result):
            return asdict(result)
        if isinstance(result, dict):
            return result
        if hasattr(result, "__dict__"):
            # remove atributos privados
            return {k: v for k, v in result.__dict__.items() if not k.startswith("_")}
        # fallback genérico
        return {"raw_result": str(result)}

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
        # 6) Serialização de saída (robusta)
        # ------------------------------------------------------------------
        # Se result não existe, criamos um dict padrão
        if 'result' not in locals() or result is None:
            payload = {
                "request_id": request_id,
                "filial_id": getattr(pre, "filial_id", None),
                "status": "erro",
            }
        else:
            payload = getattr(result, "__dict__", None) or asdict(result)
            payload.setdefault("request_id", request_id)
            payload.setdefault("filial_id", getattr(pre, "filial_id", None))
            payload.setdefault("status", getattr(result, "status", "erro"))

        # Campos obrigatórios do serializer
        default_fields = {
            "numero": None,
            "serie": None,
            "terminal_id": None,
            "chave_acesso": None,
            "protocolo": None,
            "xml_autorizado": None,
            "mensagem": None,
        }
        for k, v in default_fields.items():
            payload.setdefault(k, v)

        # Inicializa o serializer
        ser_out = EmitirNfceOutputSerializer(payload)

        # Audit log consistente
        audit_extra = {
            "event": "nfce_emitir",
            "tenant_id": tenant_id,
            "user_id": getattr(user, "id", None),
            "request_id": payload.get("request_id"),
            "filial_id": payload.get("filial_id"),
            "terminal_id": payload.get("terminal_id"),
            "numero": payload.get("numero"),
            "serie": payload.get("serie"),
            "status": payload.get("status"),
            "outcome": "success" if payload.get("status") == "autorizada" else "failure",
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
        """
        Fallback CRÍTICO:

        Se chegamos aqui, alguma coisa deu errado em um ponto que não foi
        capturado nas exceptions anteriores (validação, not found, permissão,
        APIException explícita).

        Antes de assumir que "falhou a comunicação com a SEFAZ" (FISCAL_5999),
        verificamos se já existe um NfceDocumento persistido para o request_id
        informado. Se existir, usamos ELE como fonte da verdade fiscal e
        devolvemos sucesso com base nesse documento, evitando:

            - XML autorizado e PDV achando que falhou.
            - documento em contingência pendente e PDV reprocessando errado.
        """

        # Tentativa best-effort de recuperar o request_id
        request_id_value = None
        try:
            # Se o serializer já foi instanciado e validado
            if "ser_in" in locals() and hasattr(ser_in, "validated_data"):
                request_id_value = ser_in.validated_data.get("request_id")
        except Exception:
            request_id_value = None

        if request_id_value is None:
            # fallback: tenta pegar direto do corpo da requisição
            request_id_value = request.data.get("request_id")

        # Tentamos o fallback fiscal SOMENTE se temos um request_id válido
        if request_id_value:
            try:
                doc = NfceDocumento.objects.filter(
                    request_id=request_id_value
                ).order_by("-created_at").first()
            except Exception:
                doc = None

            if doc is not None:
                # Construímos o DTO a partir do documento persistido
                result = _build_result_from_document(doc)
                payload = getattr(result, "__dict__", None) or asdict(result)
                ser_out = EmitirNfceOutputSerializer(payload)

                audit_extra = {
                    "event": "nfce_emitir",
                    "tenant_id": tenant_id,
                    "user_id": getattr(user, "id", None),
                    "request_id": str(getattr(result, "request_id", request_id)),
                    "filial_id": getattr(result, "filial_id", getattr(pre, "filial_id", None)),
                    "terminal_id": getattr(result, "terminal_id", None),
                    "numero": getattr(result, "numero", None),
                    "serie": getattr(result, "serie", None),
                    "status": getattr(result, "status", "erro"),
                    "outcome": "success" if result else "failure",
                }

                logger.exception(
                    "nfce_emitir_erro_pos_persistencia",
                    extra={**audit_extra, "error": str(exc)},
                )
                root_logger.exception(
                    "nfce_emitir_erro_pos_persistencia",
                    extra={**audit_extra, "error": str(exc)},
                )

                # Aqui NÃO levantamos erro: devolvemos o estado fiscal real.
                return Response(ser_out.data, status=status.HTTP_200_OK)

        # Se não foi possível localizar um documento, mantemos o comportamento original
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

