# vendas/services/vendas/adicionar_item_service.py

from __future__ import annotations

import logging
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from django.core.exceptions import ValidationError
from django.db import transaction

from metodoPagamento.models.metodo_pagamento_models import MetodoPagamento
from produtos.models.produtos_models import Produto
from usuario.models.usuario_models import User
from promocoes.models.motivo_desconto_models import MotivoDesconto
from vendas.models.venda_models import Venda, VendaStatus
from vendas.services.desconto_service import DescontoService
from vendas.services.vendas.totais_venda_service import recalcular_totais_venda
from vendas.models.venda_item_models import VendaItem

logger = logging.getLogger(__name__)


@transaction.atomic
def adicionar_item(
    *,
    venda: Venda,
    produto: Produto,
    quantidade: Decimal,
    operador: User,
    motivo_desconto: Optional[MotivoDesconto] = None,
    percentual_desconto: Optional[Decimal] = None,
    metodo_pagamento: Optional[MetodoPagamento] = None,
    aprovador: Optional[User] = None,
    operador_autenticado: bool = False,
    aprovador_autenticado: bool = False,
) -> VendaItem:
    """
    Adiciona um item ao carrinho.

    Fluxo:
    - Valida se venda está ABERTA.
    - Calcula total_bruto = preco_unitario * quantidade.
    - Cria VendaItem sem desconto inicial.
    - Se percentual_desconto > 0, delega para DescontoService.aplicar_desconto_item.
    - Recalcula totais da venda.
    """
    from decimal import Decimal as D

    if venda.status != VendaStatus.ABERTA:
        logger.warning(
            "Tentativa de adicionar item em venda não-ABERTA. venda_id=%s, status=%s",
            venda.id,
            venda.status,
        )
        raise ValidationError(
            f"Não é permitido adicionar itens quando a venda está em status {venda.status}."
        )

    if quantidade <= 0:
        raise ValidationError("Quantidade do item deve ser maior que zero.")

    preco_unitario = getattr(produto, "preco_venda", None)
    if preco_unitario is None:
        raise ValidationError("Produto não possui campo 'preco_venda' definido.")

    logger.info(
        "Adicionando item na venda. venda_id=%s, produto_id=%s, qtd=%s, preco_unit=%s, perc_desc=%s",
        venda.id,
        produto.id,
        quantidade,
        preco_unitario,
        percentual_desconto,
    )

    total_bruto = (preco_unitario * quantidade).quantize(
        D("0.01"), rounding=ROUND_HALF_UP
    )

    item = VendaItem.objects.create(
        venda=venda,
        produto=produto,
        descricao=produto.descricao,
        quantidade=quantidade,
        preco_unitario=preco_unitario,
        total_bruto=total_bruto,
        #desconto=D("0.00"),
        total_liquido=total_bruto,
    )

    # Se houver desconto solicitado, delega ao DescontoService
    print("percentual_desconto:", percentual_desconto)
    if percentual_desconto is not None and percentual_desconto > 0:
        logger.info(
            "Aplicando desconto ao item recém-criado. item_id=%s, perc_desc=%s",
            item.id,
            percentual_desconto,
        )
        item = DescontoService.aplicar_desconto_item(
            venda=venda,
            item=item,
            percentual_desconto_aplicado=percentual_desconto,
            operador=operador,
            motivo=motivo_desconto,
            metodo_pagamento=metodo_pagamento,
            aprovador=aprovador,
            operador_autenticado=operador_autenticado,
            aprovador_autenticado=aprovador_autenticado,
        )
    else:
        # Apenas recalcular totais da venda (sem desconto)
        recalcular_totais_venda(venda)

    logger.info(
        "Item adicionado com sucesso. venda_id=%s, item_id=%s, total_bruto=%s, total_liquido=%s",
        venda.id,
        item.id,
        item.total_bruto,
        item.total_liquido,
    )
    return item
