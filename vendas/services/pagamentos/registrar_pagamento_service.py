# vendas/services/pagamentos/registrar_pagamento_service.py

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Optional

from django.core.exceptions import ValidationError
from django.db import transaction


from tef.models import TefTransacao  # se estiver em outro app
from vendas.models.venda_pagamentos_models import StatusPagamento, VendaPagamento
from vendas.services.pagamentos.totais_pagamento_service import (
    recalcular_totais_pagamento,
)

logger = logging.getLogger(__name__)


@transaction.atomic
def registrar_resultado_pagamento_tef(
    *,
    pagamento: VendaPagamento,
    autorizado: bool,
    valor_autorizado: Optional[Decimal] = None,
    mensagem_retorno: Optional[str] = None,
    nsu: Optional[str] = None,
    codigo_autorizacao: Optional[str] = None,
    rede: Optional[str] = None,
    bandeira: Optional[str] = None,
    comprovante_cliente: Optional[str] = None,
    comprovante_loja: Optional[str] = None,
    resposta_crua: Optional[str] = None,
) -> VendaPagamento:
    """
    Aplica o resultado de uma transação TEF ao pagamento.

    - Só aceita pagamentos PENDENTE e utiliza_tef=True.
    - Se autorizado=True:
        * status -> AUTORIZADO
        * valor_autorizado (default: valor_solicitado)
        * atualiza totais da venda
    - Se autorizado=False:
        * status -> NEGADO
        * não altera totais da venda
    - Sempre registra/atualiza TefTransacao com dados recebidos.
    """
    if not pagamento.utiliza_tef:
        raise ValidationError("Pagamento informado não utiliza TEF.")

    if pagamento.status != StatusPagamento.PENDENTE:
        raise ValidationError(
            f"Somente pagamentos PENDENTES podem ter resultado TEF registrado. "
            f"Status atual: {pagamento.status}."
        )

    logger.info(
        "Registrando resultado TEF. pagamento_id=%s, autorizado=%s, valor_solicitado=%s",
        pagamento.id,
        autorizado,
        pagamento.valor_solicitado,
    )

    if autorizado:
        pagamento.status = StatusPagamento.AUTORIZADO
        pagamento.valor_autorizado = (
            valor_autorizado or pagamento.valor_solicitado
        )
    else:
        pagamento.status = StatusPagamento.NEGADO
        pagamento.valor_autorizado = Decimal("0.00")

    if mensagem_retorno:
        pagamento.mensagem_retorno = mensagem_retorno

    pagamento.save(
        update_fields=[
            "status",
            "valor_autorizado",
            "mensagem_retorno",
            "atualizado_em",
        ]
    )

    # TEF em model separada
    tef_data = {
        "nsu": nsu,
        "codigo_autorizacao": codigo_autorizacao,
        "rede": rede,
        "bandeira": bandeira,
        "comprovante_cliente": comprovante_cliente,
        "comprovante_loja": comprovante_loja,
        "resposta_crua": resposta_crua,
    }

    # cria ou atualiza a TefTransacao associada
    TefTransacao.objects.update_or_create(
        pagamento=pagamento,
        defaults=tef_data,
    )

    # se autorizado, atualiza totais da venda
    if autorizado:
        recalcular_totais_pagamento(pagamento.venda)

    logger.info(
        "Resultado TEF registrado. pagamento_id=%s, novo_status=%s, valor_autorizado=%s",
        pagamento.id,
        pagamento.status,
        pagamento.valor_autorizado,
    )

    return pagamento
