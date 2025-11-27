# vendas/services/vendas/remover_item_service.py

from __future__ import annotations

import logging

from django.core.exceptions import ValidationError
from django.db import transaction

from vendas.models.venda_models import Venda, VendaStatus
from vendas.models.venda_item_models import VendaItem
from vendas.services.vendas.totais_venda_service import recalcular_totais_venda

logger = logging.getLogger(__name__)


@transaction.atomic
def remover_item(*, venda: Venda, item: VendaItem) -> None:
    """
    Remove um item do carrinho e recalcula os totais.

    Se o carrinho ficar vazio, a venda continua ABERTA, porém com totais zerados.
    """
    if venda.status != VendaStatus.ABERTA:
        logger.warning(
            "Tentativa de remover item em venda não-ABERTA. venda_id=%s, status=%s",
            venda.id,
            venda.status,
        )
        raise ValidationError(
            f"Não é permitido remover itens quando a venda está em status {venda.status}."
        )

    logger.info(
        "Removendo item da venda. venda_id=%s, item_id=%s", venda.id, item.id
    )

    item.delete()
    recalcular_totais_venda(venda)

    logger.info(
        "Item removido. venda_id=%s, novos_totais: bruto=%s, desc=%s, liquido=%s",
        venda.id,
        venda.total_bruto,
        venda.total_desconto,
        venda.total_liquido,
    )
