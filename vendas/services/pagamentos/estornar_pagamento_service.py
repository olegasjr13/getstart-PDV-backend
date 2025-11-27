# vendas/services/pagamentos/estornar_pagamento_service.py

from __future__ import annotations

import logging

from django.core.exceptions import ValidationError
from django.db import transaction

from usuario.models.usuario_models import User
from vendas.models.venda_pagamentos_models import StatusPagamento, VendaPagamento
from vendas.services.pagamentos.totais_pagamento_service import recalcular_totais_pagamento

logger = logging.getLogger(__name__)


@transaction.atomic
def estornar_pagamento(*, pagamento: VendaPagamento, motivo: str | None = None) -> VendaPagamento:
    """
    Estorna um pagamento AUTORIZADO.

    Regras:
    - Apenas pagamentos com status AUTORIZADO podem ser estornados aqui.
    - TEF: depois (E4) podemos criar uma camada específica que chama
      o estorno TEF e, em seguida, esse service para registrar.
    """
    venda = pagamento.venda

    if pagamento.status != StatusPagamento.AUTORIZADO:
        logger.warning(
            "Tentativa de estorno de pagamento em status inválido. pagamento_id=%s, status=%s",
            pagamento.id,
            pagamento.status,
        )
        raise ValidationError(
            f"Somente pagamentos AUTORIZADOS podem ser estornados por este fluxo. Status atual: {pagamento.status}."
        )

    logger.info(
        "Estornando pagamento. pagamento_id=%s, venda_id=%s, valor_aut=%s, troco=%s, motivo=%s",
        pagamento.id,
        venda.id,
        pagamento.valor_autorizado,
        pagamento.valor_troco,
        motivo,
    )

    pagamento.status = StatusPagamento.ESTORNADO
    if motivo:
        pagamento.mensagem_retorno = motivo
    pagamento.save(update_fields=["status", "mensagem_retorno", "atualizado_em"])

    recalcular_totais_pagamento(venda=venda)

    logger.info(
        "Pagamento estornado. pagamento_id=%s, novo_status=%s, venda.total_pago=%s, venda.total_troco=%s",
        pagamento.id,
        pagamento.status,
        venda.total_pago,
        venda.total_troco,
    )
    return pagamento

def estornar_pagamento_local(
    *,
    pagamento: VendaPagamento,
    operador: User,
    motivo: str | None = None,
    aprovador: User | None = None,
) -> VendaPagamento:
    """
    Estorna um pagamento local (não TEF) respeitando a configuração do TERMINAL.

    Regras:
    - Só estorna pagamentos AUTORIZADOS.
    - Lê a configuração terminal.solicitar_senha_estorno:
        * False -> qualquer operador pode estornar.
        * True  -> exige 'aprovador' diferente do operador
                  (simulando senha de supervisor/gerente).
    - Reutiliza a lógica central de estorno (estornar_pagamento).
    """
    venda = pagamento.venda
    terminal = venda.terminal

    if pagamento.utiliza_tef:
        raise ValidationError(
            "Pagamento TEF não deve ser estornado por este fluxo. "
            "Use o fluxo específico de estorno TEF."
        )

    if pagamento.status != StatusPagamento.AUTORIZADO:
        raise ValidationError("Só é possível estornar pagamentos autorizados.")

    logger.info(
        "Solicitação de estorno LOCAL: pagamento_id=%s, venda_id=%s, operador_id=%s, terminal_id=%s",
        pagamento.id,
        venda.id,
        operador.id,
        terminal.id,
    )

    if terminal.solicitar_senha_estorno:
        if aprovador is None:
            raise ValidationError(
                "Este terminal exige aprovação/senha de supervisor para estornar pagamentos."
            )

        if aprovador.id == operador.id:
            raise ValidationError(
                "A aprovação de estorno deve ser realizada por um usuário diferente do operador."
            )

        logger.info(
            "Estorno LOCAL aprovado por supervisor/aprovador_id=%s para pagamento_id=%s.",
            aprovador.id,
            pagamento.id,
        )

    # Chama o fluxo central de estorno já existente
    estornar_pagamento(pagamento=pagamento, motivo=motivo)

    logger.info(
        "Estorno LOCAL concluído. pagamento_id=%s, novo_status=%s, venda_id=%s total_pago=%s total_troco=%s",
        pagamento.id,
        pagamento.status,
        venda.id,
        venda.total_pago,
        venda.total_troco,
    )

    return pagamento
