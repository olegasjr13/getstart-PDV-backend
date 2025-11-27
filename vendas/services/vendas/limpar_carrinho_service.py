# vendas/services/vendas/limpar_carrinho_service.py

from __future__ import annotations

import logging
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from vendas.models.venda_models import Venda, VendaStatus

logger = logging.getLogger(__name__)


@transaction.atomic
def limpar_carrinho(venda: Venda) -> None:
    """
    Remove TODOS os itens da venda e zera os totais.

    Venda permanece em status ABERTA.
    """
    if venda.status != VendaStatus.ABERTA:
        logger.warning(
            "Tentativa de limpar carrinho em venda não-ABERTA. venda_id=%s, status=%s",
            venda.id,
            venda.status,
        )
        raise ValidationError(
            f"Não é permitido limpar carrinho quando a venda está em status {venda.status}."
        )

    logger.info("Limpando carrinho. venda_id=%s", venda.id)

    venda.itens.all().delete()
    venda.total_bruto = Decimal("0.00")
    venda.total_desconto = Decimal("0.00")
    venda.total_liquido = Decimal("0.00")
    venda.save(update_fields=["total_bruto", "total_desconto", "total_liquido"])

    logger.info("Carrinho limpo. venda_id=%s", venda.id)
