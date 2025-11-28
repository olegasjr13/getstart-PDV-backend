# vendas/services/vendas/abrir_venda_service.py

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Optional

from django.db import transaction
from django.forms import ValidationError

from caixa.models.caixa_models import Caixa
from filial.models.filial_models import Filial
from terminal.models.terminal_models import Terminal
from usuario.models.usuario_models import User
from vendas.models.venda_models import Venda, VendaStatus, TipoVenda, TipoDocumentoFiscal

logger = logging.getLogger(__name__)


@transaction.atomic
def abrir_venda(
    *,
    filial: Filial,
    terminal: Terminal,
    operador: User,
    tipo_venda: str = TipoVenda.VENDA_NORMAL,
    documento_fiscal_tipo: str = TipoDocumentoFiscal.NFCE,
    request_id: Optional[str] = None,
    observacoes: Optional[str] = None,
) -> Venda:
    """
    Abre uma nova venda (carrinho) para um terminal/filial/operador.

    - Inicia com status=ABERTA.
    - Totais = 0.
    - Sem itens.
    """
    logger.info(
        "Abrindo nova venda. filial_id=%s, terminal_id=%s, operador_id=%s, "
        "tipo_venda=%s, doc_fiscal=%s",
        filial.id,
        terminal.id,
        operador.id,
        tipo_venda,
        documento_fiscal_tipo,
    )

    caixa_aberto = (
        Caixa.objects.filter(
            filial=filial,
            terminal=terminal,
            status=Caixa.Status.ABERTO,
        )
        .order_by("-aberto_em")
        .first()
    )

    if caixa_aberto is None:
        logger.info(
            "Erro ao abrir venda: não há caixa aberto para o terminal. filial_id=%s terminal_id=%s",
            filial.id,
            terminal.id,
        )
        raise ValidationError("Não há caixa aberto para este terminal.")



    venda = Venda(
        filial=filial,
        terminal=terminal,
        operador=operador,
        tipo_venda=tipo_venda,
        documento_fiscal_tipo=documento_fiscal_tipo,
        status=VendaStatus.ABERTA,
        total_bruto=Decimal("0.00"),
        total_desconto=Decimal("0.00"),
        total_liquido=Decimal("0.00"),
        total_pago=Decimal("0.00"),
        total_troco=Decimal("0.00"),
        request_id=request_id,
        observacoes=observacoes,
        caixa=caixa_aberto,
    )

    venda.clean()
    venda.save()

    logger.info("Venda aberta com sucesso. venda_id=%s", venda.id)
    return venda
