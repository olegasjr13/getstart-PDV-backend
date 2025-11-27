# fiscal/services/nfce_venda_service.py

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Optional, Union
from uuid import UUID, uuid4

from django.db import transaction
from django.apps import apps

from rest_framework.exceptions import ValidationError

from filial.models.filial_models import Filial
from terminal.models.terminal_models import Terminal
from usuario.models.usuario_models import User
from vendas.models.venda_models import Venda, VendaStatus, TipoDocumentoFiscal
from vendas.models.venda_item_models import VendaItem
from vendas.models.venda_pagamentos_models import (
    VendaPagamento,
    StatusPagamento,
)

from fiscal.services.numero_service import reservar_numero_nfce
from fiscal.services.pre_emissao_service import (
    criar_pre_emissao,
    PreEmissaoResult,
)
from fiscal.services.emissao_service import (
    emitir_nfce,
    EmitirNfceResult,
    SefazClientProtocol,
)

logger = logging.getLogger("pdv.fiscal")


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------


def _decimal_to_float(value: Optional[Decimal]) -> float:
    if value is None:
        return 0.0
    return float(value)


def _montar_payload_nfce_de_venda(venda: Venda) -> dict:
    """
    Constrói um payload JSON a partir da Venda, para ser armazenado em NfcePreEmissao.payload.

    Esse payload será usado posteriormente pelo serviço de emissão para montar o XML.
    A ideia é ser autoexplicativo e estável.
    """
    itens_payload = []
    for item in venda.itens.all():  # related_name="itens"
        assert isinstance(item, VendaItem)

        itens_payload.append(
            {
                "id": str(item.id),
                "produto_id": str(item.produto_id),
                "descricao": getattr(item, "descricao", "") or "",
                "quantidade": _decimal_to_float(getattr(item, "quantidade", None)),
                "preco_unitario": _decimal_to_float(
                    getattr(item, "preco_unitario", None)
                ),
                "total_bruto": _decimal_to_float(getattr(item, "total_bruto", None)),
                "percentual_desconto_aplicado": _decimal_to_float(
                    getattr(item, "percentual_desconto_aplicado", None)
                ),
                "desconto": _decimal_to_float(getattr(item, "desconto", None)),
                "total_liquido": _decimal_to_float(
                    getattr(item, "total_liquido", None)
                ),
            }
        )

    pagamentos_payload = []
    for pg in venda.pagamentos.all():  # related_name="pagamentos"
        assert isinstance(pg, VendaPagamento)

        pagamentos_payload.append(
            {
                "id": str(pg.id),
                "metodo_pagamento_id": str(pg.metodo_pagamento_id),
                "status": pg.status,
                "utiliza_tef": pg.utiliza_tef,
                "valor_solicitado": _decimal_to_float(pg.valor_solicitado),
                "valor_autorizado": _decimal_to_float(pg.valor_autorizado),
                "valor_troco": _decimal_to_float(pg.valor_troco),
                "mensagem_retorno": pg.mensagem_retorno or "",
            }
        )

    payload = {
        "venda": {
            "id": str(venda.id),
            "status": venda.status,
            "documento_fiscal_tipo": venda.documento_fiscal_tipo,
            "filial_id": str(venda.filial_id),
            "terminal_id": str(venda.terminal_id),
            "total_bruto": _decimal_to_float(venda.total_bruto or Decimal("0.00")),
            "total_desconto": _decimal_to_float(
                getattr(venda, "total_desconto", None) or Decimal("0.00")
            ),
            "total_liquido": _decimal_to_float(
                venda.total_liquido or Decimal("0.00")
            ),
        },
        "itens": itens_payload,
        "pagamentos": pagamentos_payload,
    }

    return payload


def _obter_serie_nfce_do_terminal(terminal: Terminal) -> int:
    """
    Obtém a série NFC-e a ser usada para o terminal.

    Preferência:
      1) terminal.serie
      2) terminal.serie_nfce
      3) default = 1 (com WARNING em log)

    Isso evita AttributeError em produção e, ao mesmo tempo,
    gera trilha de auditoria quando a série não está configurada.
    """
    serie = getattr(terminal, "serie", None)

    if not serie and hasattr(terminal, "serie_nfce"):
        serie = getattr(terminal, "serie_nfce", None)

    if not serie:
        serie = 1
        logger.warning(
            "Terminal sem série NFC-e configurada. Usando série default=1. terminal_id=%s",
            terminal.id,
        )

    try:
        return int(serie)
    except (TypeError, ValueError):
        logger.error(
            "Valor inválido de série NFC-e no terminal. terminal_id=%s serie_raw=%r",
            terminal.id,
            serie,
        )
        raise ValidationError(
            {
                "code": "FISCAL_1007",
                "message": "Série NFC-e inválida configurada para o terminal.",
            }
        )


def _validar_pagamentos_para_nfce(venda: Venda) -> None:
    """
    Regras mínimas de pagamentos para permitir pré-emissão NFC-e.

    Objetivo:
      - Garantir que há pagamentos autorizados.
      - Garantir que o valor efetivamente recebido (autorizações - troco)
        cobre o total líquido da venda.
    """
    pagamentos = list(venda.pagamentos.all())

    if not pagamentos:
        raise ValidationError(
            {
                "code": "FISCAL_1006",
                "message": "Venda não possui pagamentos registrados para emissão NFC-e.",
            }
        )

    total_autorizado = Decimal("0.00")
    for pg in pagamentos:
        assert isinstance(pg, VendaPagamento)
        autorizado = pg.valor_autorizado or Decimal("0.00")
        troco = pg.valor_troco or Decimal("0.00")
        total_autorizado += autorizado - troco

    total_liquido = venda.total_liquido or Decimal("0.00")

    if total_autorizado <= Decimal("0.00"):
        raise ValidationError(
            {
                "code": "FISCAL_1007",
                "message": "Não há pagamentos autorizados para a venda.",
            }
        )

    if total_autorizado < total_liquido:
        raise ValidationError(
            {
                "code": "FISCAL_1008",
                "message": "Total de pagamentos autorizados é inferior ao total líquido da venda.",
            }
        )


def _validar_venda_para_nfce(venda: Venda) -> None:
    """
    Regras mínimas para permitir pré-emissão NFC-e a partir de uma Venda.
    Ajuste se necessário, mas a ideia é sempre falhar ANTES de tocar em número / SEFAZ.
    """
    # Tipo de documento fiscal
    if venda.documento_fiscal_tipo != TipoDocumentoFiscal.NFCE:
        logger.warning(
            "Tentativa de pré-emissão NFC-e com documento_fiscal_tipo inválido. "
            "venda_id=%s tipo=%s",
            venda.id,
            venda.documento_fiscal_tipo,
        )
        raise ValidationError(
            {
                "code": "FISCAL_1001",
                "message": "Venda não está configurada para NFC-e.",
            }
        )

    # Status da venda – aqui assumo que, para pré-emissão, ela já está com pagamento ok
    # ou aguardando emissão fiscal. Ajuste se seu fluxo permitir outros estados.
    if venda.status not in {
        VendaStatus.PAGAMENTO_CONFIRMADO,
        VendaStatus.AGUARDANDO_EMISSAO_FISCAL,
    }:
        logger.warning(
            "Tentativa de pré-emissão NFC-e com status de venda inválido. "
            "venda_id=%s status=%s",
            venda.id,
            venda.status,
        )
        raise ValidationError(
            {
                "code": "FISCAL_1002",
                "message": f"Venda em status '{venda.status}' não pode ir para pré-emissão NFC-e.",
            }
        )

    # Totais
    total_liquido = venda.total_liquido or Decimal("0.00")
    if total_liquido <= Decimal("0.00"):
        raise ValidationError(
            {
                "code": "FISCAL_1003",
                "message": "Não é possível pré-emitir NFC-e para venda sem total líquido positivo.",
            }
        )

    # Filial / Terminal
    if not venda.filial_id:
        raise ValidationError(
            {
                "code": "FISCAL_1004",
                "message": "Venda não possui filial vinculada.",
            }
        )

    if not venda.terminal_id:
        raise ValidationError(
            {
                "code": "FISCAL_1005",
                "message": "Venda não possui terminal vinculado.",
            }
        )

    # Valida pagamentos (cobertura financeira da venda)
    _validar_pagamentos_para_nfce(venda)


# ---------------------------------------------------------------------------
# 1) Pré-emissão NFC-e a partir de uma Venda
# ---------------------------------------------------------------------------


@transaction.atomic
def nfce_pre_emissao(
    *,
    venda: Venda,
    operador: User,
    request_id: Optional[Union[str, UUID]] = None,
) -> PreEmissaoResult:
    """
    Orquestra a PRÉ-EMISSÃO NFC-e a partir de uma Venda.

    Fluxo:
      1. Valida se a venda pode gerar NFC-e (tipo, status, totais, pagamentos).
      2. Normaliza o request_id (UUID).
      3. Usa reservar_numero_nfce para garantir série/número de forma segura.
      4. Monta payload a partir da Venda (itens + pagamentos).
      5. Chama criar_pre_emissao(user, request_id, payload) – que é idempotente.
      6. Retorna PreEmissaoResult.
    """

    # Recarrega venda sob lock, garantindo consistência com estados/liquidação
    venda = (
        Venda.objects.select_for_update()
        .select_related("filial", "terminal")
        .get(pk=venda.pk)
    )

    logger.info(
        "nfce_pre_emissao iniciada. venda_id=%s status_venda=%s request_id=%s",
        venda.id,
        venda.status,
        request_id,
    )

    _validar_venda_para_nfce(venda)

    # Normaliza o request_id para UUID (e gera um se vier None)
    if request_id is None:
        req_uuid = uuid4()
    else:
        req_uuid = UUID(str(request_id))

    terminal: Terminal = venda.terminal
    filial: Filial = venda.filial

    serie_nfce = _obter_serie_nfce_do_terminal(terminal)

    # -------------------------------------------------------------------
    # 1) Reserva de número NFC-e (idempotente por request_id)
    # -------------------------------------------------------------------
    logger.info(
        "Reservando número NFC-e. venda_id=%s terminal_id=%s serie=%s request_id=%s",
        venda.id,
        terminal.id,
        serie_nfce,
        req_uuid,
    )

    reserva_result = reservar_numero_nfce(
        user=operador,
        terminal_id=str(terminal.id),
        serie=serie_nfce,
        request_id=str(req_uuid),
    )

    logger.info(
        "Número NFC-e reservado. venda_id=%s numero=%s serie=%s terminal_id=%s filial_id=%s",
        venda.id,
        reserva_result.numero,
        reserva_result.serie,
        reserva_result.terminal_id,
        reserva_result.filial_id,
    )

    # -------------------------------------------------------------------
    # 2) Monta payload da NFC-e a partir da Venda
    # -------------------------------------------------------------------
    payload = _montar_payload_nfce_de_venda(venda)

    # -------------------------------------------------------------------
    # 3) Cria / reutiliza pré-emissão (idempotente por request_id)
    # -------------------------------------------------------------------
    pre_result = criar_pre_emissao(
        user=operador,
        request_id=str(req_uuid),
        payload=payload,
    )

    logger.info(
        "Pré-emissão NFC-e concluída. venda_id=%s pre_emissao_id=%s numero=%s serie=%s",
        venda.id,
        pre_result.id,
        pre_result.numero,
        pre_result.serie,
    )

    return pre_result


# ---------------------------------------------------------------------------
# 2) Facade: emitir NFC-e a partir da Venda (pré-emissão + SEFAZ)
# ---------------------------------------------------------------------------


def emitir_nfce_para_venda(
    *,
    venda: Venda,
    operador: User,
    sefaz_client: SefazClientProtocol,
    request_id: Optional[Union[str, UUID]] = None,
) -> EmitirNfceResult:
    """
    Facade de ALTO NÍVEL para emissão NFC-e a partir de uma Venda.

    Passos:
      1) nfce_pre_emissao → garante NfcePreEmissao consistente com a venda.
      2) emitir_nfce(user, request_id, sefaz_client) → chama SEFAZ / API fiscal,
         persiste NfceDocumento + auditoria.
      3) Retorna EmitirNfceResult (com chave, protocolo, status, xml, etc).

    Idempotência:
      - nfce_pre_emissao é idempotente por request_id.
      - emitir_nfce também é idempotente por NfceDocumento.request_id (não reemite na SEFAZ).
    """

    # Normaliza ou gera request_id
    if request_id is None:
        req_uuid = uuid4()
    else:
        req_uuid = UUID(str(request_id))

    logger.info(
        "emitir_nfce_para_venda chamado. venda_id=%s request_id=%s",
        venda.id,
        req_uuid,
    )

    # 1) Pré-emissão (reserva + NfcePreEmissao)
    pre_result = nfce_pre_emissao(
        venda=venda,
        operador=operador,
        request_id=req_uuid,
    )

    # 2) Emissão NFC-e (comunicação SEFAZ / API fiscal)
    result = emitir_nfce(
        user=operador,
        request_id=req_uuid,
        sefaz_client=sefaz_client,
    )

    logger.info(
        "emitir_nfce_para_venda concluído. venda_id=%s numero=%s serie=%s status_nfce=%s pre_emissao_id=%s",
        venda.id,
        result.numero,
        result.serie,
        result.status,
        getattr(pre_result, "id", None),
    )

    return result
