# vendas/services/pagamentos/dto.py

from dataclasses import dataclass
from decimal import Decimal
from typing import List
from uuid import UUID


@dataclass
class ResumoPagamento:
    pagamento_id: str
    metodo_pagamento_id: str
    descricao_metodo: str
    valor_solicitado: Decimal
    valor_autorizado: Decimal
    valor_troco: Decimal
    status: str


@dataclass
class ResumoPagamentosVenda:
    venda_id: str
    total_liquido_venda: Decimal
    total_pago: Decimal
    total_troco: Decimal
    saldo_a_pagar: Decimal
    pagamentos: List[ResumoPagamento]
