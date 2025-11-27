# tef/clients/base.py

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol, Optional

from vendas.models.venda_pagamentos_models import VendaPagamento
from terminal.models.terminal_models import Terminal


@dataclass
class TefIniciarRequest:
    """
    Dados necessários para iniciar uma transação TEF.
    """

    pagamento: VendaPagamento
    terminal: Terminal
    valor: Decimal
    moeda: str = "986"  # BRL (ISO 4217 numérico)
    tipo_transacao: str = "VENDA"  # ex: VENDA, CANCELAMENTO, etc.
    identificador_pdv: Optional[str] = None
    # Pode ser expandido com mais campos conforme o binário/sitef exigir


@dataclass
class TefIniciarResult:
    """
    Resultado imediato da chamada de início TEF.
    Representa o que o binário/sitef devolve na "iniciação" (não o resultado final).
    """

    sucesso_comunicacao: bool
    nsu_sitef: Optional[str] = None
    nsu_host: Optional[str] = None
    codigo_retorno: Optional[str] = None
    mensagem_retorno: Optional[str] = None
    raw_request: Optional[str] = None
    raw_response: Optional[str] = None


class TefClientProtocol(Protocol):
    """
    Contrato que qualquer cliente TEF (SITEF, Cielo, Stone, mock, etc.)
    deve seguir para iniciar uma transação.
    """

    def iniciar_transacao(self, req: TefIniciarRequest) -> TefIniciarResult:
        ...
