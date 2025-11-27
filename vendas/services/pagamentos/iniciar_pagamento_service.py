# vendas/services/pagamentos/iniciar_pagamento_service.py

from __future__ import annotations

import logging
from decimal import Decimal
from django.db.models import Q

from django.db import transaction
from django.forms import ValidationError

from metodoPagamento.models.metodo_pagamento_models import MetodoPagamento
from tef.models.tef_transacao_models import TefTransacao
from usuario.models.usuario_models import User
from vendas.models import Venda, VendaPagamento, StatusPagamento
from vendas.services.pagamentos.validar_pagamento_service import (
    validar_pagamento_simples,
)
from vendas.services.pagamentos.totais_pagamento_service import (
    recalcular_totais_pagamento,
)

logger = logging.getLogger(__name__)


@transaction.atomic
def iniciar_pagamento(
    *,
    venda: Venda,
    metodo_pagamento: MetodoPagamento,
    valor: Decimal,
    operador: User,
    usar_tef: bool | None = None,
) -> VendaPagamento:
    """
    Inicia um pagamento para a venda.

    - Se usar_tef=True => cria pagamento PENDENTE e TEF fará a autorização.
    - Se usar_tef=False => pagamento já nasce AUTORIZADO (ex: dinheiro).
    - Se usar_tef=None => decide com base em metodo_pagamento.utiliza_tef.
    """

    if usar_tef is None:
        usar_tef = metodo_pagamento.utiliza_tef

    logger.info(
        "Iniciando pagamento. venda_id=%s, metodo_pagamento_id=%s, valor=%s, usar_tef=%s",
        venda.id,
        metodo_pagamento.id,
        valor,
        usar_tef,
    )

    # Valida regras básicas (status da venda, saldo, se permite troco, etc.)
    validar_pagamento_simples(
        venda=venda,
        metodo_pagamento=metodo_pagamento,
        valor=valor,
    )

    from decimal import Decimal as D

    if usar_tef:
        # Pagamento TEF: fica PENDENTE aguardando retorno do TEF
        pagamento = VendaPagamento.objects.create(
            venda=venda,
            metodo_pagamento=metodo_pagamento,
            valor_solicitado=valor,
            valor_autorizado=None,
            valor_troco=D("0.00"),
            status=StatusPagamento.PENDENTE,
            utiliza_tef=True,  # <<< SNAPSHOT FUNDAMENTAL
        )

        logger.info(
            "Pagamento TEF iniciado. pagamento_id=%s, venda_id=%s, status=%s",
            pagamento.id,
            venda.id,
            pagamento.status,
        )
        return pagamento

    # Pagamento NÃO TEF: autorização imediata
    saldo_atual = venda.saldo_a_pagar  # usamos helper da Venda

    valor_autorizado = valor
    valor_troco = D("0.00")

    if metodo_pagamento.permite_troco and valor > saldo_atual:
        valor_autorizado = saldo_atual
        valor_troco = (valor - saldo_atual).quantize(D("0.01"))

    pagamento = VendaPagamento.objects.create(
        venda=venda,
        metodo_pagamento=metodo_pagamento,
        valor_solicitado=valor,
        valor_autorizado=valor_autorizado,
        valor_troco=valor_troco,
        status=StatusPagamento.AUTORIZADO,
        utiliza_tef=False,  # <<< SNAPSHOT EXPLÍCITO
    )

    # Atualiza totais da venda
    recalcular_totais_pagamento(venda=venda)

    logger.info(
        "Pagamento não TEF autorizado. pagamento_id=%s, venda_id=%s, "
        "valor_autorizado=%s, troco=%s, total_pago=%s",
        pagamento.id,
        venda.id,
        pagamento.valor_autorizado,
        pagamento.valor_troco,
        venda.total_pago,
    )

    return pagamento

@transaction.atomic
def registrar_pagamento_service(
    *,
    pagamento: VendaPagamento,
    autorizado: bool,
    nsu_sitef: str | None = None,
    nsu_host: str | None = None,
    codigo_autorizacao: str | None = None,
    codigo_retorno: str | None = None,
    mensagem_retorno: str | None = None,
    valor_confirmado: Decimal | None = None,
    raw_request: str | None = None,
    raw_response: str | None = None,
) -> VendaPagamento:
    """
    Registra o resultado de um pagamento TEF.

    Agora com:
    - transação atômica;
    - select_for_update na Venda;
    - idempotência por NSU (nsu_sitef/nsu_host).
    """
    from decimal import Decimal as D

    logger.info(
        "Registrando resultado de pagamento TEF: pagamento_id=%s autorizado=%s nsu_sitef=%s nsu_host=%s codigo_retorno=%s mensagem_retorno=%s",
        pagamento.id,
        autorizado,
        nsu_sitef,
        nsu_host,
        codigo_retorno,
        mensagem_retorno,
    )

    if not pagamento.utiliza_tef:
        raise ValidationError("Este pagamento não é TEF. Use o fluxo de pagamento local.")

    if pagamento.status != StatusPagamento.PENDENTE:
        # Idempotência básica: se já não está mais pendente, apenas retornamos o estado atual
        logger.info(
            "Pagamento TEF não está mais PENDENTE (status=%s). "
            "Tratando chamada como idempotente.",
            pagamento.status,
        )
        return pagamento

    venda = (
        Venda.objects.select_for_update()
        .filter(id=pagamento.venda_id)
        .select_related("filial", "terminal")
        .get()
    )

    logger.info(
        "Venda bloqueada para atualização (select_for_update). venda_id=%s status_atual=%s saldo_a_pagar=%s",
        venda.id,
        venda.status,
        venda.saldo_a_pagar,
    )

    # ---------------------------
    # Idempotência por NSU
    # ---------------------------
    if nsu_sitef or nsu_host:
        qs_transacoes = TefTransacao.objects.filter(pagamento=pagamento)

        qs_nsu = qs_transacoes.filter(
            Q(nsu_sitef__isnull=False, nsu_sitef=nsu_sitef)
            | Q(nsu_host__isnull=False, nsu_host=nsu_host)
        )

        if qs_nsu.exists():
            # Já existe transação registrada com esse NSU para este pagamento.
            # Tratar como idempotente: apenas retornar o estado atual.
            logger.warning(
                "Chamada TEF idempotente detectada: pagamento_id=%s nsu_sitef=%s nsu_host=%s. "
                "Mantendo status=%s.",
                pagamento.id,
                nsu_sitef,
                nsu_host,
                pagamento.status,
            )
            return pagamento

    # Atualiza campos TEF no pagamento
    pagamento.nsu_sitef = nsu_sitef
    pagamento.nsu_host = nsu_host
    pagamento.codigo_autorizacao = codigo_autorizacao
    pagamento.codigo_retorno = codigo_retorno
    pagamento.mensagem_retorno = mensagem_retorno

    if autorizado:
        if valor_confirmado is None:
            valor_confirmado = pagamento.valor_solicitado
           
        pagamento.valor_autorizado = D(valor_confirmado)
        pagamento.status = StatusPagamento.AUTORIZADO
    else:
        pagamento.status = StatusPagamento.NEGADO
        pagamento.valor_autorizado = None
        pagamento.valor_troco = D("0.00")


    pagamento.save(
        update_fields=[
            "nsu_sitef",
            "nsu_host",
            "codigo_autorizacao",
            "codigo_retorno",
            "mensagem_retorno",
            "valor_autorizado",
            "valor_troco",
            "status",
        ]
    )

    # Registra/atualiza TefTransacao com os dados do retorno
    transacao, created = TefTransacao.objects.get_or_create(
        pagamento=pagamento,
        defaults={
            "venda": venda,
            "filial": venda.filial,
            "terminal": venda.terminal,
            "nsu_sitef": nsu_sitef,
            "nsu_host": nsu_host,
            "codigo_autorizacao": codigo_autorizacao,
            "codigo_retorno": codigo_retorno,
            "mensagem_retorno": mensagem_retorno,
            "valor_confirmado": valor_confirmado,
            "valor_transacao": valor_confirmado,
            "raw_request": raw_request,
            "raw_response": raw_response,
        },
    )

    if not created:
        transacao.nsu_sitef = nsu_sitef
        transacao.nsu_host = nsu_host
        transacao.codigo_autorizacao = codigo_autorizacao
        transacao.codigo_retorno = codigo_retorno
        transacao.mensagem_retorno = mensagem_retorno
        transacao.valor_confirmado = valor_confirmado
        transacao.valor_transacao = valor_confirmado
        transacao.raw_request = raw_request
        transacao.raw_response = raw_response
        transacao.save(
            update_fields=[
                "nsu_sitef",
                "nsu_host",
                "codigo_autorizacao",
                "codigo_retorno",
                "mensagem_retorno",
                "valor_confirmado",
                "valor_transacao",
                "raw_request",
                "raw_response",
            ]
        )

    # Atualiza totais da venda se autorizado
    if pagamento.status == StatusPagamento.AUTORIZADO:
        

        recalcular_totais_pagamento(venda=venda, salvar=True)

    logger.info(
        "Resultado final do pagamento TEF registrado: pagamento_id=%s status=%s valor_autorizado=%s venda_id=%s total_pago=%s saldo_a_pagar=%s",
        pagamento.id,
        pagamento.status,
        pagamento.valor_autorizado,
        venda.id,
        venda.total_pago,
        venda.saldo_a_pagar,
    )

    return pagamento