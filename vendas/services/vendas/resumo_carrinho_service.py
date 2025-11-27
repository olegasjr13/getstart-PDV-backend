# vendas/services/vendas/resumo_carrinho_service.py

from __future__ import annotations

import logging

from vendas.models.venda_models import Venda
from vendas.services.vendas.dto import ResumoCarrinho, ResumoItemCarrinho

logger = logging.getLogger(__name__)


def obter_resumo_carrinho(venda: Venda) -> ResumoCarrinho:
    """
    Retorna um snapshot da venda/carrinho em uma estrutura simples, ideal
    para a camada de API / frontend.
    """
    itens_resumo = []

    for it in venda.itens.all().order_by("created_at"):
        itens_resumo.append(
            ResumoItemCarrinho(
                item_id=str(it.id),
                produto_id=str(it.produto_id),
                descricao=it.descricao,
                quantidade=it.quantidade,
                preco_unitario=it.preco_unitario,
                total_bruto=it.total_bruto,
                desconto=it.desconto,
                total_liquido=it.total_liquido,
                percentual_desconto_aplicado=it.percentual_desconto_aplicado,
            )
        )

    resumo = ResumoCarrinho(
        venda_id=str(venda.id),
        filial_id=str(venda.filial_id),
        terminal_id=str(venda.terminal_id),
        operador_id=str(venda.operador_id),
        status=venda.status,
        total_bruto=venda.total_bruto,
        total_desconto=venda.total_desconto,
        total_liquido=venda.total_liquido,
        itens=itens_resumo,
    )

    logger.info(
        "Resumo do carrinho gerado. venda_id=%s, total_itens=%s, bruto=%s, desc=%s, liquido=%s",
        venda.id,
        len(itens_resumo),
        venda.total_bruto,
        venda.total_desconto,
        venda.total_liquido,
    )
    return resumo
