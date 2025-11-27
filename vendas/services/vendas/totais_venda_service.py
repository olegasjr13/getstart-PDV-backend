# vendas/services/vendas/totais_venda_service.py

from __future__ import annotations

import logging

from django.db import transaction

from vendas.models.venda_models import Venda
from vendas.services.desconto_service import DescontoService

logger = logging.getLogger(__name__)


@transaction.atomic
def recalcular_totais_venda(venda: Venda, salvar: bool = True) -> Venda:
    """
    Wrapper para centralizar o recálculo dos totais da venda.
    Delegamos para DescontoService.recalcular_totais_venda, mas mantemos
    logs em um ponto único.
    """
    logger.info(
        "Recalculando totais da venda. venda_id=%s (antes: bruto=%s, desc=%s, liquido=%s)",
        venda.id,
        venda.total_bruto,
        venda.total_desconto,
        venda.total_liquido,
    )

    venda_atualizada = DescontoService.recalcular_totais_venda(venda, salvar=salvar)

    logger.info(
        "Totais da venda recalculados. venda_id=%s (depois: bruto=%s, desc=%s, liquido=%s)",
        venda_atualizada.id,
        venda_atualizada.total_bruto,
        venda_atualizada.total_desconto,
        venda_atualizada.total_liquido,
    )
    return venda_atualizada
