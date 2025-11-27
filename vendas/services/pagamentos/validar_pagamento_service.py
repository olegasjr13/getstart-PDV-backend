# vendas/services/pagamentos/validar_pagamento_service.py

from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError

from vendas.models.venda_models import Venda
from metodoPagamento.models.metodo_pagamento_models import MetodoPagamento


def validar_pagamento_simples(
    *,
    venda: Venda,
    metodo_pagamento: MetodoPagamento,
    valor: Decimal,
) -> None:
    if valor is None or valor <= 0:
        raise ValidationError("Valor do pagamento deve ser maior que zero.")

    if not venda.esta_aberta_para_pagamento():
        raise ValidationError("Venda não está em status que permita pagamento.")

    saldo_atual = venda.saldo_a_pagar

    if valor > saldo_atual and not metodo_pagamento.permite_troco:
        raise ValidationError(
            "Valor do pagamento excede o saldo a pagar e o método selecionado não permite troco."
        )
