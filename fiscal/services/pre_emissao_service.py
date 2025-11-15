# fiscal/services/pre_emissao_service.py
import logging
from dataclasses import dataclass
from django.db import transaction
from django.utils import timezone

from fiscal.models import NfceNumeroReserva
from fiscal.models.pre_emissao_models import NfcePreEmissao
from filial.models.filial_models import Filial

logger = logging.getLogger("pdv.fiscal")

ERR_PREEMISSAO_DUPLICADA = "FISCAL_4001"
ERR_RESERVA_NAO_ENCONTRADA = "FISCAL_4002"
ERR_A1_EXPIRED = "FISCAL_3001"


@dataclass
class PreEmissaoResult:
    id: str
    numero: int
    serie: int
    filial_id: str
    terminal_id: str
    request_id: str
    payload: dict
    created_at: str


def _assert_a1_valid(filial):
    if not filial.a1_expires_at or filial.a1_expires_at <= timezone.now():
        from rest_framework.exceptions import PermissionDenied
        raise PermissionDenied({"code": ERR_A1_EXPIRED, "message": "Certificado A1 expirado."})


def criar_pre_emissao(*, user, request_id, payload) -> PreEmissaoResult:
    """
    Regras:
    - Reserva de número deve existir.
    - Nenhuma pré-emissão pode existir com o mesmo request_id.
    - Certificado A1 da filial deve estar válido.
    - Idempotência: se pré-emissão já existir, retorná-la.
    """

    # 1) Recupera reserva
    try:
        reserva = NfceNumeroReserva.objects.get(request_id=request_id)
    except NfceNumeroReserva.DoesNotExist:
        from rest_framework.exceptions import NotFound
        raise NotFound({"code": ERR_RESERVA_NAO_ENCONTRADA, "message": "Número não reservado."})

    # 2) Valida A1
    filial = Filial.objects.only("a1_expires_at").get(id=reserva.filial_id)
    _assert_a1_valid(filial)

    # 3) Idempotência — se já existe pré-emissão, retorna
    try:
        pre = NfcePreEmissao.objects.get(request_id=request_id)
        return PreEmissaoResult(
            id=str(pre.id),
            numero=pre.numero,
            serie=pre.serie,
            filial_id=str(pre.filial_id),
            terminal_id=str(pre.terminal_id),
            request_id=str(pre.request_id),
            payload=pre.payload,
            created_at=pre.created_at.isoformat(),
        )
    except NfcePreEmissao.DoesNotExist:
        pass

    # 4) Cria nova pré-emissão (transação)
    with transaction.atomic():
        pre = NfcePreEmissao.objects.create(
            filial_id=reserva.filial_id,
            terminal_id=reserva.terminal_id,
            numero=reserva.numero,
            serie=reserva.serie,
            request_id=request_id,
            payload=payload,
        )

    return PreEmissaoResult(
        id=str(pre.id),
        numero=pre.numero,
        serie=pre.serie,
        filial_id=str(pre.filial_id),
        terminal_id=str(pre.terminal_id),
        request_id=str(pre.request_id),
        payload=pre.payload,
        created_at=pre.created_at.isoformat(),
    )
