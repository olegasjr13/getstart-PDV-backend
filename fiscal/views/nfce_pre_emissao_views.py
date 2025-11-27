# fiscal/views/nfce_pre_emissao_views.py

import uuid
import logging

from django.apps import apps

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from fiscal.services.numero_service import _assert_a1_valid

logger = logging.getLogger("pdv.fiscal")


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def pre_emissao(request):
    """
    Pré-emissão da NFC-e a partir de uma reserva existente.

    Fluxo (happy path):
    - request.data deve conter:
        * request_id: UUID usado na reserva de número.
        * demais campos livres (itens, total, observacao, etc.) => payload.
    - Busca NfceNumeroReserva pelo request_id.
    - Valida vínculo user↔filial da reserva.
    - Valida que o certificado A1 da filial está válido.
    - Cria (ou reaproveita) NfcePreEmissao (idempotência por request_id).
    - Retorna:
        * 201 na primeira pré-emissão
        * 200 em chamadas subsequentes
      Sempre com:
        numero, serie, filial_id, terminal_id, request_id, payload.
    """

    # -------------------------------------------------------------------
    # 1) Validação básica do request_id
    # -------------------------------------------------------------------
    data = request.data or {}
    raw_req_id = data.get("request_id")

    if not raw_req_id:
        return Response(
            {"request_id": ["Este campo é obrigatório."]},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        request_id = uuid.UUID(str(raw_req_id))
    except (TypeError, ValueError):
        return Response(
            {"request_id": ["Não é um UUID válido."]},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # payload = tudo que não for request_id (guardamos como está)
    payload = dict(data)
    payload.pop("request_id", None)

    # -------------------------------------------------------------------
    # 2) Carrega models de forma desacoplada
    # -------------------------------------------------------------------
    NfceNumeroReserva = apps.get_model("fiscal", "NfceNumeroReserva")
    NfcePreEmissao = apps.get_model("fiscal", "NfcePreEmissao")
    Filial = apps.get_model("filial", "Filial")

    # -------------------------------------------------------------------
    # 3) Busca reserva existente para o request_id
    #    (sem select_related, porque NfceNumeroReserva não tem FKs reais)
    # -------------------------------------------------------------------
    try:
        reserva = NfceNumeroReserva.objects.get(request_id=request_id)
    except NfceNumeroReserva.DoesNotExist:
        raise NotFound(
            {
                "code": "FISCAL_4001",
                "message": "Reserva de número não encontrada para este request_id.",
            }
        )

    user = request.user
    filial_id = reserva.filial_id

    # -------------------------------------------------------------------
    # 4) Permissão: usuário deve estar vinculado à filial da reserva
    # -------------------------------------------------------------------
    if not user.userfilial_set.filter(filial_id=filial_id).exists():
        raise PermissionDenied(
            {
                "code": "AUTH_1006",
                "message": "Usuário sem permissão para a filial do terminal",
            }
        )

    # -------------------------------------------------------------------
    # 5) Validação do certificado A1 da filial
    # -------------------------------------------------------------------
    _assert_a1_valid(Filial.objects.get(id=filial_id))
    


    # -------------------------------------------------------------------
    # 6) Idempotência da pré-emissão por request_id
    #    NfcePreEmissao guarda *_id, não FKs, então usamos terminal_id/filial_id.
    # -------------------------------------------------------------------
    defaults = {
        "terminal_id": reserva.terminal_id,
        "filial_id": reserva.filial_id,
        "numero": reserva.numero,
        "serie": reserva.serie,
        "payload": payload,
    }

    pre_obj, created = NfcePreEmissao.objects.get_or_create(
        request_id=request_id,
        defaults=defaults,
    )

    # -------------------------------------------------------------------
    # 7) Resposta de domínio
    # -------------------------------------------------------------------
    response_data = {
        "numero": reserva.numero,
        "serie": reserva.serie,
        "filial_id": str(reserva.filial_id),
        "terminal_id": str(reserva.terminal_id),
        "request_id": str(reserva.request_id),
        "payload": payload,
    }

    status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK

    logger.info(
        "nfce_pre_emissao",
        extra={
            "event": "nfce_pre_emissao",
            "tenant_id": getattr(getattr(request, "tenant", None), "schema_name", None),
            "user_id": getattr(request.user, "id", None),
            "filial_id": str(filial_id),
            "terminal_id": str(reserva.terminal_id),
            "serie": reserva.serie,
            "numero": reserva.numero,
            "request_id": str(request_id),
            "outcome": "created" if created else "reused",
        },
    )

    return Response(response_data, status=status_code)
