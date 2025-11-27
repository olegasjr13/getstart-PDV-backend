# vendas/services/pagamentos/totais_pagamento_service.py

from __future__ import annotations

import logging
from decimal import Decimal

from django.db import transaction

from vendas.models import Venda, VendaPagamento, StatusPagamento
from vendas.models.venda_models import VendaStatus

logger = logging.getLogger(__name__)


@transaction.atomic
def recalcular_totais_pagamento(*, venda: Venda, salvar: bool = True) -> None:
    """
    Recalcula os totais de pagamento da venda (total_pago e total_troco)
    com base nos pagamentos AUTORIZADOS.

    Além disso, ajusta o status da venda de forma consistente:

    - Se não há pagamentos autorizados: mantém status atual.
    - Se há pagamentos autorizados e saldo_a_pagar > 0:
        - Se status estiver ABERTA, passa para AGUARDANDO_PAGAMENTO.
    - Se saldo_a_pagar <= 0 (venda totalmente paga):
        - Se status estiver em {ABERTA, AGUARDANDO_PAGAMENTO},
          passa para PAGAMENTO_CONFIRMADO.
    """
    from decimal import Decimal as D

    logger.info("Recalculando totais de pagamento para venda_id=%s", venda.id)

    pagamentos_autorizados = venda.pagamentos.filter(
        status=StatusPagamento.AUTORIZADO
    )

    total_pago = D("0.00")
    total_troco = D("0.00")

    for pagamento in pagamentos_autorizados:
        total_pago += pagamento.valor_liquido_para_total
        total_troco += pagamento.valor_troco or D("0.00")

    logger.info(
        "Totais de pagamento antes do recálculo: total_pago=%s, total_troco=%s",
        venda.total_pago,
        venda.total_troco,
    )

    venda.total_pago = total_pago.quantize(D("0.01"))
    venda.total_troco = total_troco.quantize(D("0.01"))

    logger.info(
        "Totais de pagamento após recálculo (antes de salvar): total_pago=%s, total_troco=%s",
        venda.total_pago,
        venda.total_troco,
    )

    if not salvar:
        return

    # ---------------------------------------------------------
    # Atualiza status da venda de acordo com a situação de pagamento
    # ---------------------------------------------------------
    status_original = venda.status

    saldo_atual = venda.saldo_a_pagar

    if venda.total_pago <= D("0.00"):
        # Nenhum pagamento efetivo ainda: não alteramos o status
        logger.info(
            "Nenhum pagamento autorizado para venda_id=%s. "
            "Status permanece inalterado: %s",
            venda.id,
            venda.status,
        )
        update_fields = ["total_pago", "total_troco"]
    else:
        # Já houve pelo menos um pagamento autorizado
        if saldo_atual > D("0.00"):
            # Ainda falta pagar uma parte da venda
            if venda.status == VendaStatus.ABERTA:
                venda.status = VendaStatus.AGUARDANDO_PAGAMENTO
        else:
            # saldo_a_pagar <= 0 => venda totalmente paga
            if venda.status in {VendaStatus.ABERTA, VendaStatus.AGUARDANDO_PAGAMENTO}:
                venda.status = VendaStatus.PAGAMENTO_CONFIRMADO

        update_fields = ["total_pago", "total_troco"]
        if venda.status != status_original:
            update_fields.append("status")

        logger.info(
            "Status da venda_id=%s após recálculo de pagamentos: %s (antes era %s). "
            "saldo_a_pagar=%s",
            venda.id,
            venda.status,
            status_original,
            saldo_atual,
        )

    venda.save(update_fields=update_fields)

