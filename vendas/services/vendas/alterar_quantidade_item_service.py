# vendas/services/vendas/alterar_quantidade_item_service.py

from __future__ import annotations

import logging
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from django.core.exceptions import ValidationError
from django.db import transaction

from metodoPagamento.models.metodo_pagamento_models import MetodoPagamento
from promocoes.models.motivo_desconto_models import MotivoDesconto
from usuario.models.usuario_models import User
from vendas.models.venda_item_models import VendaItem
from vendas.models.venda_models import Venda,  VendaStatus
from vendas.services.desconto_service import DescontoService
from vendas.services.vendas.totais_venda_service import recalcular_totais_venda

logger = logging.getLogger(__name__)


@transaction.atomic
def alterar_quantidade_item(
    *,
    venda: Venda,
    item: VendaItem,
    nova_quantidade: Decimal,
    operador: User,
    motivo_desconto: Optional[MotivoDesconto] = None,
    metodo_pagamento: Optional[MetodoPagamento] = None,
    aprovador: Optional[User] = None,
    operador_autenticado: bool = False,
    aprovador_autenticado: bool = False,
) -> VendaItem:
    """
    Altera a quantidade de um item já existente no carrinho.

    Regras:
    - Venda deve estar ABERTA.
    - nova_quantidade > 0.
    - Recalcula total_bruto.
    - Se o item já tinha percentual_desconto_aplicado, reaplica o MESMO percentual
      usando DescontoService (respeitando limites).
    - Se não tinha desconto ou percentual=0 -> sem desconto.
    """
    from decimal import Decimal as D

    if venda.status != VendaStatus.ABERTA:
        logger.warning(
            "Tentativa de alterar quantidade em venda não-ABERTA. venda_id=%s, status=%s",
            venda.id,
            venda.status,
        )
        raise ValidationError(
            f"Não é permitido alterar itens quando a venda está em status {venda.status}."
        )

    if nova_quantidade <= 0:
        raise ValidationError("Nova quantidade deve ser maior que zero.")
    
    perc_antigo = item.percentual_desconto_aplicado

    logger.info(
        "Alterando quantidade de item. venda_id=%s, item_id=%s, qtd_atual=%s, nova_qtd=%s, perc_antigo=%s",
        venda.id,
        item.id,
        item.quantidade,
        nova_quantidade,
        perc_antigo,
    )

    item.quantidade = nova_quantidade
    item.total_bruto = (item.preco_unitario * nova_quantidade).quantize(
        D("0.01"), rounding=ROUND_HALF_UP
    )
    # zera desconto momentaneamente; será recalculado abaixo, se for o caso
    item.percentual_desconto_aplicado = D("0.00")
    item.total_liquido = item.total_bruto
    item.save(
        update_fields=["quantidade", "total_bruto", "percentual_desconto_aplicado", "total_liquido"]
    )


    if perc_antigo is not None and perc_antigo > 0:
        logger.info(
            "Reaplicando percentual de desconto antigo no item após alterar quantidade. "
            "item_id=%s, perc_antigo=%s",
            item.id,
            perc_antigo,
        )
        if motivo_desconto is None:
            motivo_desconto = item.motivo_desconto

        item = DescontoService.aplicar_desconto_item(
            venda=venda,
            item=item,
            percentual_desconto_aplicado=perc_antigo,
            operador=operador,
            motivo=motivo_desconto,
            metodo_pagamento=metodo_pagamento,
            aprovador=aprovador,
            operador_autenticado=operador_autenticado,
            aprovador_autenticado=aprovador_autenticado,
        )
    else:
        recalcular_totais_venda(venda)

    logger.info(
        "Quantidade alterada com sucesso. venda_id=%s, item_id=%s, nova_qtd=%s, total_bruto=%s, total_liquido=%s",
        venda.id,
        item.id,
        item.quantidade,
        item.total_bruto,
        item.total_liquido,
    )
    return item
