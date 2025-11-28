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
import hashlib
import json

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

    def emitir_nfce(self, *, pre_emissao: NfcePreEmissao) -> Dict[str, Any]:
        """
        Deve retornar um dict com, no mínimo:

          - status: str (autorizada / rejeitada / etc)
          - chave_acesso: str | None
          - protocolo: str | None
          - xml_autorizado: str | None
          - mensagem: str | None
          - raw: dict (payload bruto da SEFAZ)

        Em caso de erro técnico (timeout, indisponibilidade etc),
        deve levantar SefazTechnicalError.
        """
        ...


# ---------------------------------------------------------------------------
# DTO de saída
# ---------------------------------------------------------------------------

@dataclass
class EmitirNfceResult:
    """
    DTO de retorno da emissão de NFC-e.

    Inclui flag em_contingencia para diferenciar:
      - Emissão normal (autorizada/rejeitada).
      - Emissão em contingência (sem comunicação bem-sucedida com a SEFAZ).
    """

    request_id: str
    numero: int
    serie: int
    filial_id: str
    terminal_id: str

    chave_acesso: Optional[str]
    protocolo: Optional[str]
    status: str

    xml_autorizado: Optional[str] = None
    mensagem: Optional[str] = None
    raw_sefaz: Optional[Dict[str, Any]] = None
    em_contingencia: bool = False


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _get_tenant_schema_from_user(user: User) -> Optional[str]:
    """
    Extrai o schema do tenant a partir do usuário, se disponível.
    """
    return getattr(getattr(user, "tenant", None), "schema_name", None)


def _build_result_from_document(doc: NfceDocumento) -> EmitirNfceResult:
    """
    Constrói o DTO EmitirNfceResult a partir de um NfceDocumento existente.

    Regras:
      - Para documentos em contingência, o DTO não expõe a chave dummy
        salva apenas para satisfazer o NOT NULL do banco.
    """
    em_contingencia = getattr(doc, "em_contingencia", False)

    if em_contingencia:
        chave_acesso = None
        protocolo = None
        xml_autorizado = None
    else:
        chave_acesso = doc.chave_acesso
        protocolo = doc.protocolo or ""
        xml_autorizado = getattr(doc, "xml_autorizado", None)

    raw = getattr(doc, "raw_sefaz_response", None)

    return EmitirNfceResult(
        request_id=str(doc.request_id),
        numero=doc.numero,
        serie=doc.serie,
        filial_id=str(doc.filial_id),
        terminal_id=str(doc.terminal_id),
        chave_acesso=chave_acesso,
        protocolo=protocolo,
        status=doc.status,
        xml_autorizado=xml_autorizado,
        mensagem=getattr(doc, "mensagem_sefaz", None),
        raw_sefaz=raw,
        em_contingencia=em_contingencia,
    )


def _make_dummy_chave_acesso() -> str:
    """
    Gera uma chave de acesso dummy para cenários de contingência.

    Objetivos:
      - Nunca ser NULL (satisfaz NOT NULL do banco).
      - Ter tamanho compatível com o campo (44 chars).
      - Ser única o suficiente para não bater em UNIQUE, caso exista.
    """
    # 1 char de prefixo + 43 chars de uuid → 44 caracteres
    return "C" + uuid.uuid4().hex[:43]
def _hash_payload(payload: Any) -> str:
    """
    Gera um hash estável (SHA256) do payload enviado ao parceiro fiscal.

    - Normaliza o JSON com sort_keys=True para ser independente da ordem das chaves.
    - Se o payload não for serializável em JSON, usa str(payload) como fallback.
    """
    try:
        normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    except TypeError:
        normalized = str(payload)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


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
    Fluxo de emissão NFC-e a partir de uma pré-emissão consolidada.

    Regras principais:

      1. Localiza NfcePreEmissao pelo request_id.
      2. Garante vínculo user ↔ filial (via UserFilial).
      3. Garante certificado A1 válido (_assert_a1_valid).
      4. Idempotência forte por NfceDocumento.request_id:
         - Se já existir NfceDocumento, não chama parceiro fiscal de novo.
      5. Chama sefaz_client.emitir_nfce(pre_emissao=...).
      6. Persiste NfceDocumento + NfceAuditoria em transação atômica:
         - Emissão normal (autorizada/rejeitada).
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
            pre = NfcePreEmissao.objects.select_for_update().get(
                request_id=request_id
            )
        except NfcePreEmissao.DoesNotExist:
            logger.error(
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

        # Payload enviado ao parceiro fiscal
        payload_enviado = pre.payload
        hash_payload_enviado = _hash_payload(payload_enviado)

        # -------------------------------------------------------------------
        # 2) Carrega Filial / Terminal
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
        # 3) Vínculo usuário ↔ filial (mesma regra do numero_service)
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
        # 4) A1 válido (mesma semântica da pré-emissão / reserva)
        # -------------------------------------------------------------------
        _assert_a1_valid(filial)

        # -------------------------------------------------------------------
        # 5) Idempotência por NfceDocumento.request_id
        # -------------------------------------------------------------------
        print("DEBUG checando idempotência para request_id:", request_id)
        existing = (
            NfceDocumento.objects
            .filter(request_id=request_id)
            .order_by("-created_at")
            .first()
        )
        if existing is not None:
            # Não chama parceiro fiscal novamente; devolve estado consolidado.
            logger.info(
                "emitir_nfce_idempotente_reuso_documento",
                extra={
                    "event": "nfce_emitir",
                    "tenant_id": tenant_schema,
                    "user_id": getattr(user, "id", None),
                    "request_id": str(request_id),
                    "nfce_documento_id": str(existing.id),
                    "status": existing.status,
                },
            )
            return _build_result_from_document(existing)
        print("DEBUG idempotência: nenhum documento existente, prosseguindo...")
        # -------------------------------------------------------------------
        # 6) Chamada parceiro fiscal — tratamento diferenciado para falha técnica
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
        # 6.A) Falha técnica → CONTINGÊNCIA PENDENTE
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
                # chave dummy, nunca nula (campo NOT NULL/UNIQUE)
                chave_acesso=_make_dummy_chave_acesso(),
                protocolo="",
                status="contingencia_pendente",
                mensagem_sefaz=mensagem_tech,
                xml_autorizado=None,
                raw_sefaz_response=raw_tech,
                ambiente=ambiente,
                uf=uf,
                em_contingencia=True,
                contingencia_ativada_em=now,
                contingencia_motivo=mensagem_tech,
                contingencia_regularizada_em=None,
                # campos novos – payload enviado ao parceiro
                payload_enviado=payload_enviado,
                hash_payload_enviado=hash_payload_enviado,
            )

            NfceAuditoria.objects.create(
                tipo_evento="EMISSAO_CONTINGENCIA_ATIVADA",
                nfce_documento=doc,
                tenant_id=tenant_schema,
                filial_id=filial.id,
                terminal_id=terminal.id,
                user_id=getattr(user, "id", None),
                request_id=request_id,
                codigo_retorno=str(codigo_tech),
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
        # 6.B) Emissão normal (autorizada / rejeitada)
        # -------------------------------------------------------------------
        if sefaz_resp is None:
            # Defensivo: não deveria acontecer, mas evita quebrar o fluxo.
            raise APIException(
                detail={
                    "code": "FISCAL_5001",
                    "message": "Parceiro fiscal não retornou resposta nem erro técnico.",
                }
            )

        # Normaliza resposta do parceiro
        status_resp = str(sefaz_resp.get("status") or "").lower()
        chave_acesso = sefaz_resp.get("chave_acesso")
        protocolo = sefaz_resp.get("protocolo")
        xml_autorizado = sefaz_resp.get("xml_autorizado")
        mensagem = sefaz_resp.get("mensagem")
        raw = sefaz_resp.get("raw") or sefaz_resp
        codigo_retorno = sefaz_resp.get("codigo_retorno")

        # Heurística simples para classificar autorizado/rejeitado
        autorizado = False
        if status_resp in {"autorizada", "autorizado", "aut"}:
            autorizado = True
        if codigo_retorno in {"100", "150"}:
            autorizado = True

        if autorizado:
            doc_status = "autorizada"
            tipo_evento = "EMISSAO_AUTORIZADA"
            outcome = "autorizada"
        else:
            doc_status = status_resp or "rejeitada"
            tipo_evento = "EMISSAO_REJEITADA"
            outcome = "rejeitada"

        doc = NfceDocumento.objects.create(
            filial=filial,
            terminal=terminal,
            numero=numero,
            serie=serie,
            request_id=request_id,
            chave_acesso=chave_acesso or _make_dummy_chave_acesso(),
            protocolo=protocolo or "",
            status=doc_status,
            mensagem_sefaz=mensagem,
            xml_autorizado=xml_autorizado,
            raw_sefaz_response=raw,
            ambiente=ambiente,
            uf=uf,
            em_contingencia=False,
            contingencia_ativada_em=None,
            contingencia_motivo=None,
            contingencia_regularizada_em=None,
            payload_enviado=payload_enviado,
            hash_payload_enviado=hash_payload_enviado,
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
            mensagem_retorno=mensagem,
            xml_autorizado=xml_autorizado,
            raw_sefaz_response=raw,
            ambiente=ambiente,
            uf=uf,
        )

        logger.info(
            "emitir_nfce_finalizada",
            extra={
                "event": "nfce_emitir",
                "tenant_id": tenant_schema,
                "user_id": getattr(user, "id", None),
                "request_id": str(request_id),
                "nfce_documento_id": str(doc.id),
                "status": doc.status,
                "outcome": outcome,
                "codigo_retorno": codigo_retorno,
            },
        )

        return _build_result_from_document(doc)
