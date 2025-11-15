# fiscal/services/emissao_service.py

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional, Protocol, Dict, Any
from uuid import UUID

from django.apps import apps
from django.db import transaction
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework.exceptions import NotFound, PermissionDenied, APIException

from filial.models.filial_models import Filial
from terminal.models.terminal_models import Terminal
from fiscal.models import NfcePreEmissao
from fiscal.services.numero_service import _assert_a1_valid

logger = logging.getLogger("pdv.fiscal")

User = get_user_model()


# ---------------------------------------------------------------------------
# Tipagem do cliente SEFAZ (injeção de dependência / fácil de mockar)
# ---------------------------------------------------------------------------

class SefazClientProtocol(Protocol):
    """
    Contrato mínimo do cliente SEFAZ que o serviço espera.

    Em produção você terá uma implementação real (chamada HTTP, SOAP, etc).
    Nos testes, basta um fake que implemente esse método.
    """

    def emitir_nfce(self, *, pre_emissao: NfcePreEmissao) -> Dict[str, Any]:
        """
        Deve retornar um dict com, no mínimo, as chaves:

        - "chave_acesso": str
        - "protocolo": str
        - "status": str  (ex: "autorizada", "rejeitada", "erro")
        - "xml_autorizado": str | None
        - "mensagem": str | None
        - "raw": dict   (payload bruto devolvido pela SEFAZ)
        """
        ...


# ---------------------------------------------------------------------------
# DTO de saída do domínio
# ---------------------------------------------------------------------------

@dataclass
class EmitirNfceResult:
    request_id: str
    numero: int
    serie: int
    filial_id: str
    terminal_id: str

    chave_acesso: str
    protocolo: str
    status: str

    xml_autorizado: Optional[str] = None
    mensagem: Optional[str] = None
    raw_sefaz: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Repositório opcional de "documentos" (NfceDocumento)
# - Ainda não mexemos no models, então tratamos isso como opcional.
# - Quando a model for criada, o código já estará pronto para usá-la.
# ---------------------------------------------------------------------------

def _get_nfce_document_model():
    """
    Tenta obter a model 'NfceDocumento' do app fiscal.

    Se ainda não existir (models/migrations não criados), retorna None.
    Isso permite evoluir o domínio sem quebrar o projeto atual.
    """
    try:
        return apps.get_model("fiscal", "NfceDocumento")
    except LookupError:
        return None


# ---------------------------------------------------------------------------
# Função de domínio principal
# ---------------------------------------------------------------------------

def emitir_nfce(
    *,
    user: User,
    request_id: UUID,
    sefaz_client: SefazClientProtocol,
) -> EmitirNfceResult:
    """
    Fluxo de emissão NFC-e a partir de uma pré-emissão consolidada:

    1. Busca NfcePreEmissao pelo request_id.
    2. Valida vínculo user↔filial.
    3. Valida certificado A1 da filial.
    4. Idempotência:
       - Se existir NfceDocumento (quando model estiver criada) para o request_id,
         retorna o mesmo resultado.
    5. Chama o cliente SEFAZ (injeção de dependência).
    6. (Futuro) Persiste NfceDocumento com o resultado da SEFAZ.
    7. Retorna DTO EmitirNfceResult.
    """

    # -------------------------------------------------------------------
    # 1) Carrega pré-emissão
    #    (modelo atual NÃO tem FKs 'filial' / 'terminal', apenas *_id)
    # -------------------------------------------------------------------
    try:
        pre = (
            NfcePreEmissao.objects
            .only(
                "id",
                "request_id",
                "numero",
                "serie",
                "filial_id",
                "terminal_id",
                "payload",
            )
            .get(request_id=request_id)
        )
    except NfcePreEmissao.DoesNotExist:
        raise NotFound(
            {
                "code": "FISCAL_5001",
                "message": "Pré-emissão NFC-e não encontrada para este request_id.",
            }
        )

    # Busca das entidades relacionadas via *_id
    filial: Filial = Filial.objects.only("id", "a1_expires_at").get(id=pre.filial_id)
    terminal: Terminal = Terminal.objects.only("id").get(id=pre.terminal_id)

    # -------------------------------------------------------------------
    # 2) Permissão: usuário deve estar vinculado à filial
    # -------------------------------------------------------------------
    if not user.userfilial_set.filter(filial_id=filial.id).exists():
        raise PermissionDenied(
            {
                "code": "AUTH_1006",
                "message": "Usuário sem permissão para a filial da NFC-e.",
            }
        )

    # -------------------------------------------------------------------
    # 3) Certificado A1 válido
    # -------------------------------------------------------------------
    _assert_a1_valid(filial)

    # -------------------------------------------------------------------
    # 4) Idempotência via NfceDocumento (quando existir model)
    # -------------------------------------------------------------------
    NfceDocumento = _get_nfce_document_model()

    if NfceDocumento is not None:
        existing = NfceDocumento.objects.filter(request_id=request_id).first()
        if existing:
            return EmitirNfceResult(
                request_id=str(existing.request_id),
                numero=existing.numero,
                serie=existing.serie,
                filial_id=str(existing.filial_id),
                terminal_id=str(existing.terminal_id),
                chave_acesso=existing.chave_acesso,
                protocolo=existing.protocolo or "",
                status=existing.status,
                xml_autorizado=getattr(existing, "xml_autorizado", None),
                mensagem=getattr(existing, "mensagem_sefaz", None),
                raw_sefaz=getattr(existing, "raw_sefaz_response", None),
            )

    # -------------------------------------------------------------------
    # 5) Chamada SEFAZ dentro de transação
    # -------------------------------------------------------------------
    try:
        with transaction.atomic():
            sefaz_resp = sefaz_client.emitir_nfce(pre_emissao=pre)

            chave_acesso = sefaz_resp.get("chave_acesso") or ""
            protocolo = sefaz_resp.get("protocolo") or ""
            status_str = sefaz_resp.get("status") or "erro"
            xml_autorizado = sefaz_resp.get("xml_autorizado")
            mensagem = sefaz_resp.get("mensagem")
            raw = sefaz_resp.get("raw") or {}

            # Persistência futura no NfceDocumento (quando a model existir)
            if NfceDocumento is not None:
                NfceDocumento.objects.create(
                    request_id=request_id,
                    filial=filial,
                    terminal=terminal,
                    numero=pre.numero,
                    serie=pre.serie,
                    chave_acesso=chave_acesso,
                    protocolo=protocolo,
                    status=status_str,
                    xml_autorizado=xml_autorizado,
                    raw_sefaz_response=raw,
                    mensagem_sefaz=mensagem or "",
                    created_at=timezone.now(),
                )

    except Exception as exc:
        logger.exception(
            "nfce_emitir_erro",
            extra={
                "event": "nfce_emitir",
                "tenant_id": getattr(getattr(user, "tenant", None), "schema_name", None),
                "user_id": getattr(user, "id", None),
                "filial_id": str(filial.id),
                "terminal_id": str(terminal.id),
                "request_id": str(request_id),
                "error": str(exc),
            },
        )
        raise APIException(
            {
                "code": "FISCAL_5999",
                "message": "Erro ao comunicar com a SEFAZ para emissão da NFC-e.",
            }
        ) from exc

    # -------------------------------------------------------------------
    # 6) Log estruturado de sucesso
    # -------------------------------------------------------------------
    logger.info(
        "nfce_emitir",
        extra={
            "event": "nfce_emitir",
            "tenant_id": getattr(getattr(user, "tenant", None), "schema_name", None),
            "user_id": getattr(user, "id", None),
            "filial_id": str(filial.id),
            "terminal_id": str(terminal.id),
            "numero": pre.numero,
            "serie": pre.serie,
            "request_id": str(request_id),
            "chave_acesso": chave_acesso,
            "protocolo": protocolo,
            "status": status_str,
        },
    )

    # -------------------------------------------------------------------
    # 7) DTO de saída
    # -------------------------------------------------------------------
    return EmitirNfceResult(
        request_id=str(request_id),
        numero=pre.numero,
        serie=pre.serie,
        filial_id=str(filial.id),
        terminal_id=str(terminal.id),
        chave_acesso=chave_acesso,
        protocolo=protocolo,
        status=status_str,
        xml_autorizado=xml_autorizado,
        mensagem=mensagem,
        raw_sefaz=raw,
    )
