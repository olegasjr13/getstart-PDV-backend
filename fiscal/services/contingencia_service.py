from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any
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
from .emissao_service import (
    SefazClientProtocol,
    _get_tenant_schema_from_user,
    _make_dummy_chave_acesso,
)

logger = logging.getLogger("pdv.fiscal")

User = get_user_model()


# ---------------------------------------------------------------------------
# DTO de resultado da regularização de contingência
# ---------------------------------------------------------------------------

@dataclass
class RegularizarContingenciaResult:
    """
    Resultado de uma tentativa de regularização de NFC-e em contingência.

    Representa a transição de estado do documento:
      - status_antes / status_depois
      - em_contingencia_antes / em_contingencia_depois
      - regularizada=True quando a pendência de contingência foi resolvida
        (autorizada ou rejeitada de forma definitiva).
    """

    request_id: str
    numero: int
    serie: int
    filial_id: str
    terminal_id: str

    status_antes: str
    status_depois: str

    chave_acesso: Optional[str]
    protocolo: Optional[str]
    xml_autorizado: Optional[str]
    mensagem: Optional[str]
    raw_sefaz: Optional[Dict[str, Any]]

    em_contingencia_antes: bool
    em_contingencia_depois: bool
    regularizada: bool


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _get_documento_contingencia(
    *,
    documento_id: Optional[UUID | str],
    chave_acesso: Optional[str],
) -> NfceDocumento:
    """
    Localiza um NfceDocumento para regularização de contingência.

    Regras:
      - Pelo menos um dos parâmetros deve ser informado.
      - Preferência por documento_id; chave_acesso é fallback/futuro.
    """
    if not documento_id and not chave_acesso:
        raise APIException(
            {
                "code": "FISCAL_5002",
                "message": "É necessário informar documento_id ou chave_acesso para regularização de contingência.",
            }
        )

    qs = NfceDocumento.objects.select_related("filial", "terminal")

    if documento_id:
        try:
            return qs.get(id=documento_id)
        except NfceDocumento.DoesNotExist:
            raise NotFound(
                {
                    "code": "FISCAL_5003",
                    "message": "Documento NFC-e não encontrado para regularização de contingência.",
                }
            )

    # Fallback por chave de acesso (útil em integrações futuras)
    try:
        return qs.get(chave_acesso=chave_acesso)
    except NfceDocumento.DoesNotExist:
        raise NotFound(
            {
                "code": "FISCAL_5003",
                "message": "Documento NFC-e não encontrado para regularização de contingência.",
            }
        )


def _build_regularizar_result_from_doc(
    *,
    doc: NfceDocumento,
    status_antes: str,
    raw: Optional[Dict[str, Any]],
    mensagem: Optional[str],
    regularizada: bool,
) -> RegularizarContingenciaResult:
    """
    Monta o DTO RegularizarContingenciaResult a partir do estado final do documento.
    Esconde chave/protocolo/xml quando ainda em contingência.
    """
    em_contingencia_depois = getattr(doc, "em_contingencia", False)

    if em_contingencia_depois:
        chave = None
        protocolo = None
        xml = None
    else:
        chave = doc.chave_acesso
        protocolo = doc.protocolo or ""
        xml = getattr(doc, "xml_autorizado", None)

    return RegularizarContingenciaResult(
        request_id=str(doc.request_id),
        numero=doc.numero,
        serie=doc.serie,
        filial_id=str(doc.filial_id),
        terminal_id=str(doc.terminal_id),
        status_antes=status_antes,
        status_depois=doc.status,
        chave_acesso=chave,
        protocolo=protocolo,
        xml_autorizado=xml,
        mensagem=mensagem,
        raw_sefaz=raw,
        em_contingencia_antes=True if status_antes == "contingencia_pendente" else getattr(doc, "em_contingencia", False),
        em_contingencia_depois=em_contingencia_depois,
        regularizada=regularizada,
    )


# ---------------------------------------------------------------------------
# Função principal de domínio: regularização de contingência
# ---------------------------------------------------------------------------

def regularizar_contingencia_nfce(
    *,
    user: User,
    documento_id: Optional[UUID | str] = None,
    chave_acesso: Optional[str] = None,
    sefaz_client: SefazClientProtocol,
) -> RegularizarContingenciaResult:
    """
    Regulariza uma NFC-e que está em contingência (contingencia_pendente).

    Fluxos suportados:

      - Happy path (autorizada):
          status_antes = "contingencia_pendente"
          status_depois = "autorizada"
          em_contingencia_depois = False
          regularizada = True
          auditoria: EMISSAO_CONTINGENCIA_REGULARIZADA

      - Rejeitada na regularização:
          status_depois = "rejeitada_contingencia"
          em_contingencia_depois = False
          regularizada = True
          auditoria: EMISSAO_CONTINGENCIA_REJEITADA

      - Idempotência (já regularizada):
          Se status != "contingencia_pendente" OU em_contingencia=False,
          não chama SEFAZ de novo e retorna estado atual (regularizada=False).

      - Erro técnico na regularização:
          Mantém status "contingencia_pendente" / em_contingencia=True
          e levanta APIException FISCAL_5999.
    """

    # 1) Localiza o documento alvo
    doc = _get_documento_contingencia(
        documento_id=documento_id,
        chave_acesso=chave_acesso,
    )
    filial: Filial = doc.filial
    terminal: Terminal = doc.terminal
    tenant_schema = _get_tenant_schema_from_user(user)

    status_antes = doc.status
    em_contingencia_antes = getattr(doc, "em_contingencia", False)

    # 2) Permissão do usuário para a filial
    if not user.userfilial_set.filter(filial_id=filial.id).exists():
        raise PermissionDenied(
            {
                "code": "AUTH_1006",
                "message": "Usuário sem permissão para a filial da NFC-e.",
            }
        )

    # 3) Se já não está mais em contingência pendente → idempotência (não chama SEFAZ)
    if status_antes != "contingencia_pendente" or not em_contingencia_antes:
        logger.info(
            "nfce_regularizar_contingencia_idempotente",
            extra={
                "event": "nfce_regularizar_contingencia",
                "tenant_id": tenant_schema,
                "user_id": getattr(user, "id", None),
                "filial_id": str(filial.id),
                "terminal_id": str(terminal.id),
                "documento_id": str(doc.id),
                "request_id": str(doc.request_id),
                "status_atual": doc.status,
                "em_contingencia": em_contingencia_antes,
            },
        )
        return RegularizarContingenciaResult(
            request_id=str(doc.request_id),
            numero=doc.numero,
            serie=doc.serie,
            filial_id=str(doc.filial_id),
            terminal_id=str(doc.terminal_id),
            status_antes=status_antes,
            status_depois=doc.status,
            chave_acesso=None if getattr(doc, "em_contingencia", False) else doc.chave_acesso,
            protocolo=None if getattr(doc, "em_contingencia", False) else (doc.protocolo or ""),
            xml_autorizado=None if getattr(doc, "em_contingencia", False) else getattr(doc, "xml_autorizado", None),
            mensagem=getattr(doc, "mensagem_sefaz", None),
            raw_sefaz=getattr(doc, "raw_sefaz_response", None),
            em_contingencia_antes=em_contingencia_antes,
            em_contingencia_depois=getattr(doc, "em_contingencia", False),
            regularizada=False,
        )

    # 4) Certificado A1 ainda precisa estar válido
    _assert_a1_valid(filial)

    # 5) Necessário ter a pré-emissão vinculada (request_id)
    try:
        pre = NfcePreEmissao.objects.get(request_id=doc.request_id)
    except NfcePreEmissao.DoesNotExist:
        raise NotFound(
            {
                "code": "FISCAL_5004",
                "message": "Pré-emissão NFC-e não encontrada para regularização de contingência.",
            }
        )

    # 6) Chamada SEFAZ + persistência

    try:
        with transaction.atomic():
            try:
                # Reutilizamos o mesmo contrato da emissão normal
                sefaz_resp = sefaz_client.emitir_nfce(pre_emissao=pre)
            except SefazTechnicalError as exc:
                # Erro técnico: mantemos documento em contingência_pendente
                logger.warning(
                    "nfce_regularizar_contingencia_erro_tecnico",
                    extra={
                        "event": "nfce_regularizar_contingencia",
                        "tenant_id": tenant_schema,
                        "user_id": getattr(user, "id", None),
                        "filial_id": str(filial.id),
                        "terminal_id": str(terminal.id),
                        "documento_id": str(doc.id),
                        "request_id": str(doc.request_id),
                        "error": str(exc),
                        "codigo": exc.codigo,
                        "raw": exc.raw,
                    },
                )
                raise APIException(
                    {
                        "code": "FISCAL_5999",
                        "message": "Erro ao comunicar com a SEFAZ para regularizar NFC-e em contingência.",
                    }
                ) from exc

            # Interpreta resposta da SEFAZ
            status_str = sefaz_resp.get("status") or "erro"
            chave_acesso = sefaz_resp.get("chave_acesso")
            protocolo = sefaz_resp.get("protocolo")
            xml_autorizado = sefaz_resp.get("xml_autorizado")
            mensagem = sefaz_resp.get("mensagem")
            raw = sefaz_resp.get("raw") or {}

            codigo_retorno = None
            if isinstance(raw, dict) and raw.get("codigo") is not None:
                codigo_retorno = str(raw.get("codigo"))

            # Mapeia status final
            if status_str == "autorizada":
                status_final = "autorizada"
                tipo_evento = "EMISSAO_CONTINGENCIA_REGULARIZADA"
            else:
                # Rejeições em regularização são tratadas como rejeitada_contingencia
                status_final = "rejeitada_contingencia"
                tipo_evento = "EMISSAO_CONTINGENCIA_REJEITADA"

            # Atualiza documento:
            #  - Sai de contingencia_pendente
            #  - Deixa em_contingencia=False
            #  - Marca data de regularização
            doc.status = status_final
            doc.em_contingencia = False
            doc.contingencia_regularizada_em = timezone.now()

            # Se SEFAZ devolveu chave/protocolo reais, sobrepõe a dummy
            if chave_acesso:
                doc.chave_acesso = chave_acesso
            else:
                # Garante nunca ficar NULL
                if not doc.chave_acesso:
                    doc.chave_acesso = _make_dummy_chave_acesso()

            if protocolo:
                doc.protocolo = protocolo

            if xml_autorizado is not None:
                doc.xml_autorizado = xml_autorizado

            if mensagem is not None:
                doc.mensagem_sefaz = mensagem

            if raw:
                doc.raw_sefaz_response = raw

            doc.save(update_fields=[
                "status",
                "em_contingencia",
                "contingencia_regularizada_em",
                "chave_acesso",
                "protocolo",
                "xml_autorizado",
                "mensagem_sefaz",
                "raw_sefaz_response",
            ])

            # Auditoria específica da regularização
            NfceAuditoria.objects.create(
                tipo_evento=tipo_evento,
                nfce_documento=doc,
                tenant_id=tenant_schema,
                filial_id=filial.id,
                terminal_id=terminal.id,
                user_id=getattr(user, "id", None),
                request_id=doc.request_id,
                codigo_retorno=codigo_retorno,
                mensagem_retorno=mensagem or "",
                xml_autorizado=xml_autorizado,
                raw_sefaz_response=raw,
                ambiente=filial.ambiente,
                uf=filial.uf,
            )

    except APIException:
        # Já está padronizada, apenas propaga
        raise
    except Exception as exc:
        logger.exception(
            "nfce_regularizar_contingencia_erro",
            extra={
                "event": "nfce_regularizar_contingencia",
                "tenant_id": tenant_schema,
                "user_id": getattr(user, "id", None),
                "filial_id": str(filial.id),
                "terminal_id": str(terminal.id),
                "documento_id": str(doc.id),
                "request_id": str(doc.request_id),
                "error": str(exc),
            },
        )
        raise APIException(
            {
                "code": "FISCAL_5999",
                "message": "Erro ao regularizar NFC-e em contingência.",
            }
        ) from exc

    # Log final de sucesso da regularização
    logger.info(
        "nfce_regularizar_contingencia",
        extra={
            "event": "nfce_regularizar_contingencia",
            "tenant_id": tenant_schema,
            "user_id": getattr(user, "id", None),
            "filial_id": str(filial.id),
            "terminal_id": str(terminal.id),
            "documento_id": str(doc.id),
            "request_id": str(doc.request_id),
            "status_antes": status_antes,
            "status_depois": doc.status,
            "em_contingencia_antes": em_contingencia_antes,
            "em_contingencia_depois": False,
        },
    )

    return _build_regularizar_result_from_doc(
        doc=doc,
        status_antes=status_antes,
        raw=raw,
        mensagem=mensagem,
        regularizada=True,
    )
