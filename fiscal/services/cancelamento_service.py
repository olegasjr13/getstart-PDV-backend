# fiscal/services/cancelamento_service.py

import logging
from dataclasses import dataclass
from typing import Optional

from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist

from rest_framework.exceptions import NotFound, PermissionDenied, APIException

from filial.models.filial_models import Filial
from fiscal.models import NfceDocumento, NfceAuditoria

logger = logging.getLogger("pdv.fiscal")


@dataclass
class CancelarNfceResult:
    request_id: str
    filial_id: str
    terminal_id: str
    numero: int
    serie: int
    chave_acesso: str
    protocolo: str
    status: str
    mensagem: str


def _get_documento_por_referencia(
    *,
    chave_acesso: Optional[str],
    filial_id: Optional[str],
    numero: Optional[int],
    serie: Optional[int],
) -> NfceDocumento:
    """
    Localiza o NfceDocumento a ser cancelado.

    Pode usar:
      - chave_acesso
      - ou (filial_id, numero, serie)
    """

    try:
        if chave_acesso:
            return NfceDocumento.objects.select_related("filial", "terminal").get(
                chave_acesso=chave_acesso
            )

        if filial_id and numero is not None and serie is not None:
            return (
                NfceDocumento.objects.select_related("filial", "terminal")
                .filter(
                    filial_id=filial_id,
                    numero=numero,
                    serie=serie,
                )
                .get()
            )

    except ObjectDoesNotExist:
        raise NotFound(detail="Documento NFC-e não encontrado para cancelamento.")

    raise APIException(
        detail={
            "code": "FISCAL_4001",
            "message": "Parâmetros insuficientes para localizar o documento.",
        }
    )


def _assert_user_tem_acesso_filial(*, user, filial: Filial):
    """
    Valida se o usuário tem vínculo com a filial do documento.
    """
    if not user.is_authenticated:
        raise PermissionDenied("Usuário não autenticado.")

    has_link = user.userfilial_set.filter(filial_id=filial.id).exists()
    if not has_link:
        raise PermissionDenied("Usuário não tem acesso à filial da NFC-e.")


def _mock_sefaz_cancelamento(*, doc: NfceDocumento, motivo: str) -> dict:
    """
    Implementação mockada de cancelamento na SEFAZ.

    Este método será substituído futuramente por um client real (por UF/ambiente),
    mas já devolve uma estrutura coerente com o que a SEFAZ retornaria.
    """
    # Em um cenário real, aqui teríamos:
    # - montagem do XML de evento
    # - assinatura digital
    # - chamada SOAP/HTTPS para a SEFAZ
    # - parsing da resposta
    return {
        "codigo": 135,
        "protocolo": "CANCEL-" + doc.chave_acesso[-10:],
        "mensagem": "Cancelamento homologado",
    }


@transaction.atomic
def cancelar_nfce(
    *,
    user,
    chave_acesso: Optional[str],
    filial_id: Optional[str],
    numero: Optional[int],
    serie: Optional[int],
    motivo: str,
) -> CancelarNfceResult:
    """
    Cancela uma NFC-e já autorizada.

    Regras principais:
      - Só cancela documentos com status 'autorizada'.
      - Se já estiver 'cancelada', comportamento é idempotente:
        retorna os dados atuais (não chama SEFAZ de novo).
      - Registra auditoria no NfceAuditoria.
    """

    if not motivo or len(motivo.strip()) < 15:
        # Regra típica de cancelamento: motivo minimamente descritivo
        raise APIException(
            detail={
                "code": "FISCAL_4002",
                "message": "Motivo de cancelamento muito curto.",
            }
        )

    # 1) Localiza o documento
    doc = _get_documento_por_referencia(
        chave_acesso=chave_acesso,
        filial_id=filial_id,
        numero=numero,
        serie=serie,
    )

    # 2) Valida permissão do usuário
    _assert_user_tem_acesso_filial(user=user, filial=doc.filial)

    # 3) Regras de status
    if doc.status not in ("autorizada", "cancelada"):
        # Poderíamos usar um código fiscal mais específico aqui
        raise APIException(
            detail={
                "code": "FISCAL_4003",
                "message": f"Documento NFC-e em status '{doc.status}' não pode ser cancelado.",
            }
        )

    # 4) Idempotência: se já cancelada, apenas retorna
    if doc.status == "cancelada":
        logger.info(
            "nfce_cancelar_idempotente",
            extra={
                "event": "nfce_cancelar",
                "filial_id": str(doc.filial_id),
                "terminal_id": str(doc.terminal_id),
                "chave_acesso": doc.chave_acesso,
                "numero": doc.numero,
                "serie": doc.serie,
                "status": doc.status,
                "outcome": "already_cancelled",
            },
        )

        return CancelarNfceResult(
            request_id=str(doc.request_id),
            filial_id=str(doc.filial_id),
            terminal_id=str(doc.terminal_id),
            numero=doc.numero,
            serie=doc.serie,
            chave_acesso=doc.chave_acesso,
            protocolo=doc.protocolo or "",
            status=doc.status,
            mensagem=doc.mensagem_sefaz or "",
        )

    # 5) Integração SEFAZ (mock por enquanto)
    sefaz_resp = _mock_sefaz_cancelamento(doc=doc, motivo=motivo)
    codigo = sefaz_resp.get("codigo")
    protocolo = sefaz_resp.get("protocolo") or ""
    mensagem = sefaz_resp.get("mensagem") or ""

    # Aqui poderíamos validar o código retornado (ex.: 135 = cancelamento ok, outros = erro),
    # mas para o MVP fiscal vamos assumir sucesso no mock.

    # 6) Atualiza o documento
    doc.status = "cancelada"
    doc.protocolo = protocolo
    # atualiza mensagem SEFAZ para conter o texto de cancelamento
    doc.mensagem_sefaz = mensagem
    doc.save(update_fields=["status", "protocolo", "mensagem_sefaz", "updated_at"])

    # 7) Auditoria
    NfceAuditoria.objects.create(
        tipo_evento="CANCELAMENTO",
        nfce_documento=doc,
        tenant_id=None,  # pode ser ajustado quando o tenant estiver amarrado ao user/request
        filial_id=doc.filial_id,
        terminal_id=doc.terminal_id,
        user_id=getattr(user, "id", None),
        request_id=doc.request_id,
        codigo_retorno=str(codigo) if codigo is not None else None,
        mensagem_retorno=mensagem,
        xml_autorizado=None,
        raw_sefaz_response=sefaz_resp,
        ambiente=getattr(doc, "ambiente", None),
        uf=getattr(doc, "uf", None),
    )

    return CancelarNfceResult(
        request_id=str(doc.request_id),
        filial_id=str(doc.filial_id),
        terminal_id=str(doc.terminal_id),
        numero=doc.numero,
        serie=doc.serie,
        chave_acesso=doc.chave_acesso,
        protocolo=protocolo,
        status=doc.status,
        mensagem=mensagem,
    )
