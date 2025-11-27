# vendas/services/vendas/dto.py

from dataclasses import dataclass
from decimal import Decimal
from typing import List, Optional


@dataclass
class ResumoItemCarrinho:
    item_id: str
    produto_id: str
    descricao: str
    quantidade: Decimal
    preco_unitario: Decimal
    total_bruto: Decimal
    desconto: Decimal
    total_liquido: Decimal
    percentual_desconto_aplicado: Optional[Decimal]


@dataclass
class ResumoCarrinho:
    venda_id: str
    filial_id: str
    terminal_id: str
    operador_id: str
    status: str
    total_bruto: Decimal
    total_desconto: Decimal
    total_liquido: Decimal
    itens: List[ResumoItemCarrinho]
