import logging
from dataclasses import dataclass
from typing import Optional

from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist

from rest_framework.exceptions import NotFound, PermissionDenied, APIException

from filial.models.filial_models import Filial
from fiscal.models import NfceDocumento, NfceInutilizacao, NfceAuditoria
from terminal.models.terminal_models import Terminal

logger = logging.getLogger("pdv.fiscal")


@dataclass
class InutilizarFaixaNfceResult:
    request_id: str
    filial_id: str
    serie: int
    numero_inicial: int
    numero_final: int
    protocolo: str
    status: str
    mensagem: str


def _assert_user_tem_acesso_filial(*, user, filial: Filial):
    if not user.is_authenticated:
        raise PermissionDenied("Usuário não autenticado.")

    has_link = user.userfilial_set.filter(filial_id=filial.id).exists()
    if not has_link:
        raise PermissionDenied("Usuário não tem acesso à filial.")


def _mock_sefaz_inutilizacao(*, filial: Filial, serie: int, numero_inicial: int, numero_final: int, motivo: str):
    """
    Mock de inutilização na SEFAZ.

    Em produção, isso será substituído por client real.
    """
    faixa = f"{numero_inicial}-{numero_final}"
    return {
        "codigo": 102,
        "protocolo": f"INUT-{filial.uf}-{serie}-{faixa}",
        "mensagem": "Inutilização de faixa homologada (mock).",
    }


@transaction.atomic
def inutilizar_faixa_nfce(
    *,
    user,
    filial_id: str,
    serie: int,
    numero_inicial: int,
    numero_final: int,
    motivo: str,
    request_id,
) -> InutilizarFaixaNfceResult:
    """
    Inutiliza uma faixa numérica de NFC-e.

    Regras principais:
      - numero_inicial <= numero_final
      - motivo com tamanho mínimo
      - não pode haver NfceDocumento emitido na faixa
      - idempotência por request_id
    """

    if numero_inicial <= 0 or numero_final <= 0:
        raise APIException(
            detail={
                "code": "FISCAL_4100",
                "message": "Números da faixa devem ser maiores que zero.",
            }
        )

    if numero_inicial > numero_final:
        raise APIException(
            detail={
                "code": "FISCAL_4100",
                "message": "numero_inicial não pode ser maior que numero_final.",
            }
        )

    if not motivo or len(motivo.strip()) < 15:
        raise APIException(
            detail={
                "code": "FISCAL_4102",
                "message": "Motivo de inutilização muito curto (mínimo 15 caracteres).",
            }
        )

    try:
        filial = Filial.objects.get(id=filial_id)
    except ObjectDoesNotExist:
        raise NotFound("Filial não encontrada para inutilização de faixa.")

    _assert_user_tem_acesso_filial(user=user, filial=filial)

    # Idempotência: se já existe inutilização para este request_id, retorna
    try:
        existing = NfceInutilizacao.objects.get(request_id=request_id)
        return InutilizarFaixaNfceResult(
            request_id=str(existing.request_id),
            filial_id=str(existing.filial_id),
            serie=existing.serie,
            numero_inicial=existing.numero_inicial,
            numero_final=existing.numero_final,
            protocolo=existing.protocolo or "",
            status=existing.status,
            mensagem=existing.motivo,
        )
    except NfceInutilizacao.DoesNotExist:
        pass

    # Verifica se já existe inutilização para essa faixa (sem request_id)
    faixa_existente = NfceInutilizacao.objects.filter(
        filial_id=filial_id,
        serie=serie,
        numero_inicial=numero_inicial,
        numero_final=numero_final,
    ).first()

    if faixa_existente:
        # Idempotência por faixa (sem request_id), opcional
        return InutilizarFaixaNfceResult(
            request_id=str(faixa_existente.request_id),
            filial_id=str(faixa_existente.filial_id),
            serie=faixa_existente.serie,
            numero_inicial=faixa_existente.numero_inicial,
            numero_final=faixa_existente.numero_final,
            protocolo=faixa_existente.protocolo or "",
            status=faixa_existente.status,
            mensagem=faixa_existente.motivo,
        )

    # Garante que não há NfceDocumento emitido na faixa
    existe_doc_na_faixa = NfceDocumento.objects.filter(
        filial_id=filial_id,
        serie=serie,
        numero__gte=numero_inicial,
        numero__lte=numero_final,
        status__in=["autorizada", "cancelada"],
    ).exists()

    if existe_doc_na_faixa:
        raise APIException(
            detail={
                "code": "FISCAL_4101",
                "message": "Não é possível inutilizar faixa com documentos já emitidos.",
            }
        )

    # Chamada SEFAZ (mock)
    sefaz_resp = _mock_sefaz_inutilizacao(
        filial=filial,
        serie=serie,
        numero_inicial=numero_inicial,
        numero_final=numero_final,
        motivo=motivo,
    )
    codigo = sefaz_resp.get("codigo")
    protocolo = sefaz_resp.get("protocolo") or ""
    mensagem = sefaz_resp.get("mensagem") or ""

    # Persistir inutilização
    inutilizacao = NfceInutilizacao.objects.create(
        filial=filial,
        serie=serie,
        numero_inicial=numero_inicial,
        numero_final=numero_final,
        request_id=request_id,
        protocolo=protocolo,
        status="inutilizada",
        motivo=motivo,
        raw_sefaz_response=sefaz_resp,
        ambiente=getattr(filial, "ambiente", None),
        uf=filial.uf,
    )

    # Auditoria
        # Descobre um terminal da filial para registrar na auditoria
    terminal = (
        Terminal.objects.filter(filial_id=filial.id)
        .order_by("id")
        .first()
   )


    if terminal is None:
        # Em situação real, isso não deveria acontecer:
        # não faz sentido inutilizar faixa sem ter terminais cadastrados.
        raise APIException(
            detail={
                "code": "FISCAL_4103",
                "message": "Nenhum terminal encontrado para a filial na inutilização.",
            }
        )

    # Auditoria
    NfceAuditoria.objects.create(
        tipo_evento="INUTILIZACAO",
        nfce_documento=None,
        tenant_id=None,
        filial_id=filial.id,
        terminal_id=terminal.id,
        user_id=getattr(user, "id", None),
        request_id=request_id,
        codigo_retorno=str(codigo) if codigo is not None else None,
        mensagem_retorno=mensagem,
        xml_autorizado=None,
        raw_sefaz_response=sefaz_resp,
        ambiente=getattr(filial, "ambiente", None),
        uf=filial.uf,
    )



    logger.info(
        "nfce_inutilizar",
        extra={
            "event": "nfce_inutilizar",
            "filial_id": str(filial.id),
            "serie": serie,
            "numero_inicial": numero_inicial,
            "numero_final": numero_final,
            "request_id": str(request_id),
            "protocolo": protocolo,
            "status": "inutilizada",
        },
    )

    return InutilizarFaixaNfceResult(
        request_id=str(inutilizacao.request_id),
        filial_id=str(inutilizacao.filial_id),
        serie=inutilizacao.serie,
        numero_inicial=inutilizacao.numero_inicial,
        numero_final=inutilizacao.numero_final,
        protocolo=protocolo,
        status=inutilizacao.status,
        mensagem=mensagem,
    )
