# fiscal/services/emissao_service.py

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Optional, Protocol, Dict, Any
from uuid import UUID

from django.db import transaction
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework.exceptions import NotFound, PermissionDenied, APIException

from filial.models.filial_models import Filial
from terminal.models.terminal_models import Terminal
from fiscal.models import NfcePreEmissao, NfceDocumento, NfceAuditoria
from fiscal.services.numero_service import (
    _assert_a1_valid,
    ERR_NO_PERMISSION,
)
from fiscal.sefaz_clients import SefazTechnicalError

logger = logging.getLogger("pdv.fiscal")

User = get_user_model()


# ---------------------------------------------------------------------------
# Tipagem do client SEFAZ (injeção de dependência)
# ---------------------------------------------------------------------------

class SefazClientProtocol(Protocol):
    """
    Contrato mínimo do client SEFAZ que a service espera.

    Em produção você terá uma implementação real.
    Em teste/dev, usamos mocks (MockSefazClient, MockSefazClientAlwaysFail).
    """

    # fiscal/services/emissao_service.py

    def emitir_nfce(
        *,
        user: User,
        request_id: UUID,
        sefaz_client: SefazClientProtocol,
    ) -> EmitirNfceResult:
        """
        Fluxo de emissão NFC-e a partir de uma pré-emissão consolidada.

        Regras principais:

        1. Localiza NfcePreEmissao pelo request_id.
        2. Garante vínculo user ↔ filial (via UserFilial).
        3. Garante certificado A1 válido (_assert_a1_valid).
        4. Idempotência forte por NfceDocumento.request_id:
            - Se já existir NfceDocumento, não chama SEFAZ novamente.
        5. Chama sefaz_client.emitir_nfce(pre_emissao=...).
        6. Persiste NfceDocumento + NfceAuditoria em transação atômica:
            - Emissão normal (autorizada/rejeitada), ou
            - Emissão em contingência (quando SefazTechnicalError).
        7. Retorna DTO EmitirNfceResult consistente com o documento
            persistido, via _build_result_from_document.
        """

        tenant_schema = _get_tenant_schema_from_user(user)
        logger.info(
            "emitir_nfce_iniciado",
            extra={
                "event": "nfce_emitir",
                "tenant_id": tenant_schema,
                "user_id": getattr(user, "id", None),
                "request_id": str(request_id),
            },
        )

        with transaction.atomic():
            # -------------------------------------------------------------------
            # 1) Localiza pré-emissão
            # -------------------------------------------------------------------
            try:
                pre = (
                    NfcePreEmissao.objects
                    .select_for_update()
                    .select_related(None)
                    .get(request_id=request_id)
                )
            except NfcePreEmissao.DoesNotExist:
                logger.warning(
                    "emitir_nfce_pre_emissao_nao_encontrada",
                    extra={
                        "event": "nfce_emitir",
                        "tenant_id": tenant_schema,
                        "user_id": getattr(user, "id", None),
                        "request_id": str(request_id),
                    },
                )
                raise NotFound(
                    detail={
                        "code": "FISCAL_4100",
                        "message": "NfcePreEmissao não encontrada para o request_id informado.",
                    }
                )

            filial_id = pre.filial_id
            terminal_id = pre.terminal_id
            numero = pre.numero
            serie = pre.serie

            # -------------------------------------------------------------------
            # 2) Carrega Filial e Terminal (sem outer join)
            # -------------------------------------------------------------------
            try:
                filial = Filial.objects.get(id=filial_id)
            except Filial.DoesNotExist:
                logger.error(
                    "emitir_nfce_filial_nao_encontrada",
                    extra={
                        "event": "nfce_emitir",
                        "tenant_id": tenant_schema,
                        "user_id": getattr(user, "id", None),
                        "request_id": str(request_id),
                        "filial_id": str(filial_id),
                    },
                )
                raise NotFound(
                    detail={
                        "code": "FISCAL_4101",
                        "message": "Filial associada à pré-emissão não encontrada.",
                    }
                )

            try:
                terminal = Terminal.objects.get(id=terminal_id)
            except Terminal.DoesNotExist:
                logger.error(
                    "emitir_nfce_terminal_nao_encontrado",
                    extra={
                        "event": "nfce_emitir",
                        "tenant_id": tenant_schema,
                        "user_id": getattr(user, "id", None),
                        "request_id": str(request_id),
                        "terminal_id": str(terminal_id),
                    },
                )
                raise NotFound(
                    detail={
                        "code": "FISCAL_4102",
                        "message": "Terminal associado à pré-emissão não encontrado.",
                    }
                )

            # -------------------------------------------------------------------
            # 3) Vínculo usuário ↔ filial
            # -------------------------------------------------------------------
            if not user.userfilial_set.filter(filial_id=filial.id).exists():
                logger.warning(
                    "emitir_nfce_permission_denied_filial",
                    extra={
                        "event": "nfce_emitir",
                        "tenant_id": tenant_schema,
                        "user_id": getattr(user, "id", None),
                        "filial_id": str(filial.id),
                        "request_id": str(request_id),
                    },
                )
                raise PermissionDenied(
                    detail={
                        "code": ERR_NO_PERMISSION,
                        "message": "Usuário sem permissão para a filial da pré-emissão.",
                    }
                )

            # -------------------------------------------------------------------
            # 4) A1 válido
            # -------------------------------------------------------------------
            _assert_a1_valid(filial)

            # -------------------------------------------------------------------
            # 5) Idempotência por NfceDocumento.request_id
            # -------------------------------------------------------------------
            existing = (
                NfceDocumento.objects
                .filter(request_id=request_id)
                .order_by("-created_at")
                .first()
            )
            if existing is not None:
                logger.info(
                    "emitir_nfce_idempotente_reuso_documento",
                    extra={
                        "event": "nfce_emitir",
                        "tenant_id": tenant_schema,
                        "user_id": getattr(user, "id", None),
                        "request_id": str(request_id),
                        "nfce_documento_id": str(existing.id),
                        "status": existing.status,
                        "outcome": "idempotent_reuse",
                    },
                )
                return _build_result_from_document(existing)

            # -------------------------------------------------------------------
            # 6) Chamada SEFAZ
            # -------------------------------------------------------------------
            try:
                sefaz_resp = sefaz_client.emitir_nfce(pre_emissao=pre)
                tech_error: Optional[SefazTechnicalError] = None
            except SefazTechnicalError as exc:
                sefaz_resp = None
                tech_error = exc

            ambiente = getattr(filial, "ambiente", "homolog")
            uf = filial.uf

            # -------------------------------------------------------------------
            # 6.A) Falha técnica → CONTINGÊNCIA
            # -------------------------------------------------------------------
            if tech_error is not None:
                now = timezone.now()
                codigo_tech = getattr(tech_error, "codigo", "TECH_FAIL")
                mensagem_tech = str(tech_error)

                raw_tech: Dict[str, Any] = {
                    "codigo": codigo_tech,
                    "mensagem": mensagem_tech,
                }

                doc = NfceDocumento.objects.create(
                    filial=filial,
                    terminal=terminal,
                    numero=numero,
                    serie=serie,
                    request_id=request_id,
                    chave_acesso=_make_dummy_chave_acesso(),
                    protocolo="",
                    status="contingencia_pendente",
                    mensagem_sefaz=mensagem_tech,
                    codigo_retorno=str(codigo_tech) if codigo_tech is not None else None,
                    mensagem_retorno=mensagem_tech,
                    xml_autorizado=None,
                    raw_sefaz_response=raw_tech,
                    ambiente=ambiente,
                    uf=uf,
                    em_contingencia=True,
                    contingencia_ativada_em=now,
                )

                NfceAuditoria.objects.create(
                    tipo_evento="EMISSAO_CONTINGENCIA_ATIVADA",
                    nfce_documento=doc,
                    tenant_id=tenant_schema,
                    filial_id=filial.id,
                    terminal_id=terminal.id,
                    user_id=getattr(user, "id", None),
                    request_id=request_id,
                    codigo_retorno=str(codigo_tech) if codigo_tech is not None else None,
                    mensagem_retorno=mensagem_tech,
                    xml_autorizado=None,
                    raw_sefaz_response=raw_tech,
                    ambiente=ambiente,
                    uf=uf,
                )

                logger.warning(
                    "emitir_nfce_contingencia_pendente",
                    extra={
                        "event": "nfce_emitir",
                        "tenant_id": tenant_schema,
                        "user_id": getattr(user, "id", None),
                        "request_id": str(request_id),
                        "nfce_documento_id": str(doc.id),
                        "status": doc.status,
                        "outcome": "contingencia_pendente",
                    },
                )

                return _build_result_from_document(doc)

            # -------------------------------------------------------------------
            # 6.B) Caminho normal (sem falha técnica)
            # -------------------------------------------------------------------
            if not isinstance(sefaz_resp, dict):
                logger.error(
                    "emitir_nfce_resposta_invalida",
                    extra={
                        "event": "nfce_emitir",
                        "tenant_id": tenant_schema,
                        "user_id": getattr(user, "id", None),
                        "request_id": str(request_id),
                        "tipo_resposta": type(sefaz_resp).__name__,
                    },
                )
                raise APIException(
                    detail={
                        "code": "FISCAL_5001",
                        "message": "Resposta inválida da SEFAZ.",
                    }
                )

            raw = sefaz_resp.get("raw") or sefaz_resp
            status_resp = str(sefaz_resp.get("status") or "").lower()
            chave_acesso = sefaz_resp.get("chave_acesso")
            protocolo = sefaz_resp.get("protocolo") or ""
            xml_autorizado = sefaz_resp.get("xml_autorizado")
            mensagem = sefaz_resp.get("mensagem")

            codigo_retorno = None
            mensagem_retorno = mensagem
            if isinstance(raw, dict):
                codigo_retorno = raw.get("codigo", None)
                if raw.get("mensagem"):
                    mensagem_retorno = raw["mensagem"]

            if status_resp not in ("autorizada", "rejeitada"):
                status_resp = "erro"

            # Para rejeitada/erro, podemos não ter chave real → chave dummy só p/ NOT NULL
            if not chave_acesso:
                chave_acesso = _make_dummy_chave_acesso()

            doc = NfceDocumento.objects.create(
                filial=filial,
                terminal=terminal,
                numero=numero,
                serie=serie,
                request_id=request_id,
                chave_acesso=chave_acesso,
                protocolo=protocolo,
                status=status_resp,
                mensagem_sefaz=mensagem_retorno,
                codigo_retorno=str(codigo_retorno) if codigo_retorno is not None else None,
                mensagem_retorno=mensagem_retorno,
                xml_autorizado=xml_autorizado if status_resp == "autorizada" else None,
                raw_sefaz_response=raw,
                ambiente=ambiente,
                uf=uf,
                em_contingencia=False,
                contingencia_ativada_em=None,
            )

            tipo_evento = (
                "EMISSAO_AUTORIZADA"
                if status_resp == "autorizada"
                else "EMISSAO_REJEITADA"
                if status_resp == "rejeitada"
                else "EMISSAO_REGISTRADA"
            )

            NfceAuditoria.objects.create(
                tipo_evento=tipo_evento,
                nfce_documento=doc,
                tenant_id=tenant_schema,
                filial_id=filial.id,
                terminal_id=terminal.id,
                user_id=getattr(user, "id", None),
                request_id=request_id,
                codigo_retorno=str(codigo_retorno) if codigo_retorno is not None else None,
                mensagem_retorno=mensagem_retorno,
                xml_autorizado=doc.xml_autorizado,
                raw_sefaz_response=raw,
                ambiente=ambiente,
                uf=uf,
            )

            logger.info(
                "emitir_nfce_concluido",
                extra={
                    "event": "nfce_emitir",
                    "tenant_id": tenant_schema,
                    "user_id": getattr(user, "id", None),
                    "request_id": str(request_id),
                    "nfce_documento_id": str(doc.id),
                    "status": doc.status,
                    "outcome": "success" if status_resp == "autorizada" else "failure",
                },
            )

            return _build_result_from_document(doc)
