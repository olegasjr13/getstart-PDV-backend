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
from fiscal.services.numero_service import _assert_a1_valid
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


# ---------------------------------------------------------------------------
# Função de domínio principal
# ---------------------------------------------------------------------------

def emitir_nfce(*, user: User, request_id: UUID, sefaz_client: SefazClientProtocol) -> EmitirNfceResult:
    """
    Fluxo de emissão NFC-e a partir de uma pré-emissão consolidada:

      1. Busca NfcePreEmissao pelo request_id.
      2. Valida vínculo user↔filial.
      3. Valida certificado A1 da filial.
      4. Idempotência por NfceDocumento.request_id:
         - Se existir documento para o request_id, reutiliza o estado atual
           (não chama a SEFAZ novamente).
      5. Chama o cliente SEFAZ (injeção de dependência).
      6. Persiste NfceDocumento + NfceAuditoria:
         - Emissão normal (autorizada/rejeitada), ou
         - Emissão em CONTINGÊNCIA (quando SefazTechnicalError).
      7. Retorna DTO EmitirNfceResult.
    """

    # -------------------------------------------------------------------
    # 1) Carrega pré-emissão
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

    filial: Filial = Filial.objects.only("id", "a1_expires_at", "ambiente", "uf").get(id=pre.filial_id)
    terminal: Terminal = Terminal.objects.only("id").get(id=pre.terminal_id)

    tenant_schema = _get_tenant_schema_from_user(user)

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
    # 4) Idempotência via NfceDocumento.request_id
    # -------------------------------------------------------------------
    existing = (
        NfceDocumento.objects
        .filter(request_id=request_id)
        .order_by("-created_at")
        .first()
    )
    if existing:
        # Não chama a SEFAZ novamente; apenas reflete o estado atual.
        return _build_result_from_document(existing)

    # -------------------------------------------------------------------
    # 5) Chamada SEFAZ + persistência dentro de transação
    # -------------------------------------------------------------------
    try:
        with transaction.atomic():
            try:
                # Tenta emissão normal via SEFAZ
                sefaz_resp = sefaz_client.emitir_nfce(pre_emissao=pre)
            except SefazTechnicalError as exc:
                # =======================================================
                # 5.A – Erro técnico na SEFAZ → CONTINGÊNCIA
                # =======================================================
                logger.warning(
                    "nfce_emitir_contingencia_ativada",
                    extra={
                        "event": "nfce_emitir",
                        "tenant_id": tenant_schema,
                        "user_id": getattr(user, "id", None),
                        "filial_id": str(filial.id),
                        "terminal_id": str(terminal.id),
                        "request_id": str(request_id),
                        "error": str(exc),
                        "codigo": exc.codigo,
                        "raw": exc.raw,
                    },
                )

                # chave_acesso não pode ser NULL → usamos uma dummy interna
                dummy_chave = _make_dummy_chave_acesso()

                doc = NfceDocumento.objects.create(
                    request_id=request_id,
                    filial=filial,
                    terminal=terminal,
                    numero=pre.numero,
                    serie=pre.serie,
                    chave_acesso=dummy_chave,
                    protocolo="",  # sem protocolo real em contingência
                    status="contingencia_pendente",
                    xml_autorizado=None,
                    raw_sefaz_response=exc.raw,
                    mensagem_sefaz=str(exc),
                    ambiente=filial.ambiente,
                    uf=filial.uf,
                    created_at=timezone.now(),
                    em_contingencia=True,
                    contingencia_ativada_em=timezone.now(),
                    contingencia_motivo=str(exc),
                    contingencia_regularizada_em=None,
                )

                NfceAuditoria.objects.create(
                    tipo_evento="EMISSAO_CONTINGENCIA_ATIVADA",
                    nfce_documento=doc,
                    tenant_id=tenant_schema,
                    filial_id=filial.id,
                    terminal_id=terminal.id,
                    user_id=getattr(user, "id", None),
                    request_id=request_id,
                    codigo_retorno=exc.codigo or "TECH_FAIL",
                    mensagem_retorno=str(exc),
                    xml_autorizado=None,
                    raw_sefaz_response=exc.raw,
                    ambiente=filial.ambiente,
                    uf=filial.uf,
                )

                # Log estruturado final da contingência
                logger.info(
                    "nfce_emitir",
                    extra={
                        "event": "nfce_emitir",
                        "tenant_id": tenant_schema,
                        "user_id": getattr(user, "id", None),
                        "filial_id": str(filial.id),
                        "terminal_id": str(terminal.id),
                        "numero": pre.numero,
                        "serie": pre.serie,
                        "request_id": str(request_id),
                        "chave_acesso": dummy_chave,
                        "protocolo": "",
                        "status": "contingencia_pendente",
                        "em_contingencia": True,
                    },
                )

                return _build_result_from_document(doc)

            # =======================================================
            # 5.B – Emissão normal (sem erro técnico)
            # =======================================================
            chave_acesso = sefaz_resp.get("chave_acesso")
            protocolo = sefaz_resp.get("protocolo")
            status_str = sefaz_resp.get("status") or "erro"
            xml_autorizado = sefaz_resp.get("xml_autorizado")
            mensagem = sefaz_resp.get("mensagem")
            raw = sefaz_resp.get("raw") or {}

            codigo_retorno = None
            if isinstance(raw, dict) and raw.get("codigo") is not None:
                codigo_retorno = str(raw.get("codigo"))

            # Cria documento fiscal
            # Aqui também garantimos que chave/protocolo nunca sejam NULL
            doc = NfceDocumento.objects.create(
                request_id=request_id,
                filial=filial,
                terminal=terminal,
                numero=pre.numero,
                serie=pre.serie,
                chave_acesso=chave_acesso or _make_dummy_chave_acesso(),
                protocolo=protocolo or "",
                status=status_str,
                xml_autorizado=xml_autorizado,
                raw_sefaz_response=raw,
                mensagem_sefaz=mensagem or "",
                ambiente=filial.ambiente,
                uf=filial.uf,
                created_at=timezone.now(),
                em_contingencia=False,
                contingencia_ativada_em=None,
                contingencia_motivo=None,
                contingencia_regularizada_em=None,
            )

            if status_str == "autorizada":
                tipo_evento = "EMISSAO_AUTORIZADA"
            else:
                tipo_evento = "EMISSAO_REJEITADA"

            NfceAuditoria.objects.create(
                tipo_evento=tipo_evento,
                nfce_documento=doc,
                tenant_id=tenant_schema,
                filial_id=filial.id,
                terminal_id=terminal.id,
                user_id=getattr(user, "id", None),
                request_id=request_id,
                codigo_retorno=codigo_retorno,
                mensagem_retorno=mensagem or "",
                xml_autorizado=xml_autorizado,
                raw_sefaz_response=raw,
                ambiente=filial.ambiente,
                uf=filial.uf,
            )

    except APIException:
        # Já está no formato correto, apenas propaga.
        raise

    except Exception as exc:
        # Qualquer outra falha é tratada como erro geral de comunicação SEFAZ.
        logger.exception(
            "nfce_emitir_erro",
            extra={
                "event": "nfce_emitir",
                "tenant_id": tenant_schema,
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
    # 6) Log estruturado de sucesso (emissão normal)
    # -------------------------------------------------------------------
    logger.info(
        "nfce_emitir",
        extra={
            "event": "nfce_emitir",
            "tenant_id": tenant_schema,
            "user_id": getattr(user, "id", None),
            "filial_id": str(filial.id),
            "terminal_id": str(terminal.id),
            "numero": pre.numero,
            "serie": pre.serie,
            "request_id": str(request_id),
            "chave_acesso": chave_acesso,
            "protocolo": protocolo,
            "status": status_str,
            "em_contingencia": False,
        },
    )

    # -------------------------------------------------------------------
    # 7) DTO de saída (emissão normal)
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
        em_contingencia=False,
    )
