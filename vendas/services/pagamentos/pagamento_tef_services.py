# vendas/services/pagamentos/pagamento_tef_services.py

import logging
from decimal import Decimal
from typing import Optional

from django.db import transaction
from django.core.exceptions import ValidationError

from tef.models.tef_transacao_models import TefTransacao
from vendas.models.venda_models import Venda, VendaStatus
from vendas.models.venda_pagamentos_models import VendaPagamento, StatusPagamento
from metodoPagamento.models.metodo_pagamento_models import MetodoPagamento
from terminal.models.terminal_models import Terminal
from usuario.models.usuario_models import User
from tef.clients.base import TefClientProtocol, TefIniciarRequest, TefIniciarResult


from vendas.services.pagamentos.iniciar_pagamento_service import iniciar_pagamento  # ajuste o path conforme teu projeto

logger = logging.getLogger(__name__)


@transaction.atomic
def iniciar_pagamento_tef_com_cliente(
    *,
    venda: Venda,
    metodo_pagamento: MetodoPagamento,
    valor: Decimal,
    operador: User,
    terminal: Optional[Terminal] = None,
    tef_client: TefClientProtocol,
) -> VendaPagamento:
    """
    Inicia um pagamento TEF usando o cliente TEF injetado (SITEF, mock, etc).

    Passos:
    - Garante que a venda está em status que permite pagamento.
    - Garante que o método utiliza_tef=True.
    - Garante que não há outro pagamento TEF PENDENTE para a mesma venda.
    - Cria o VendaPagamento PENDENTE via iniciar_pagamento(..., usar_tef=True).
    - Chama tef_client.iniciar_transacao(...) para iniciar a transação no TEF.
    - Cria/atualiza TefTransacao com os dados retornados.
    """

    if not metodo_pagamento.utiliza_tef:
        raise ValidationError("O método de pagamento informado não está configurado para TEF.")

    if not venda.esta_aberta_para_pagamento():
        raise ValidationError("Venda não está em status que permita iniciar pagamento TEF.")

    terminal = terminal or venda.terminal

    # Impede múltiplos TEFs pendentes para a mesma venda
    existe_pendente = venda.pagamentos.filter(
        utiliza_tef=True, status=StatusPagamento.PENDENTE
    ).exists()
    if existe_pendente:
        raise ValidationError(
            "Já existe um pagamento TEF pendente para esta venda. "
            "Aguarde o retorno do TEF antes de iniciar uma nova transação."
        )

    logger.info(
        "Iniciando pagamento TEF com cliente: venda_id=%s metodo_pagamento_id=%s valor=%s terminal_id=%s operador_id=%s",
        venda.id,
        metodo_pagamento.id,
        valor,
        terminal.id,
        operador.id,
    )
    # Usa o orquestrador já existente para criar o pagamento PENDENTE
    pagamento = iniciar_pagamento(
        venda=venda,
        metodo_pagamento=metodo_pagamento,
        valor=valor,
        operador=operador,
        usar_tef=True,
    )

    logger.info(
        "Pagamento TEF criado com status PENDENTE. pagamento_id=%s, venda_id=%s",
        pagamento.id,
        venda.id,
    )

    # Monta request para o cliente TEF
    req = TefIniciarRequest(
        pagamento=pagamento,
        terminal=terminal,
        valor=valor,
        identificador_pdv=str(terminal.identificador),
    )

    # Chamada ao cliente TEF (SITEF binário / API / mock)
    result: TefIniciarResult = tef_client.iniciar_transacao(req)

    logger.info(
        "Resultado da chamada de início TEF: pagamento_id=%s sucesso_comunicacao=%s nsu_sitef=%s nsu_host=%s codigo_retorno=%s mensagem_retorno=%s",
        pagamento.id,
        result.sucesso_comunicacao,
        result.nsu_sitef,
        result.nsu_host,
        result.codigo_retorno,
        result.mensagem_retorno,
    )

    # Cria ou atualiza TefTransacao associada
    transacao, _created = TefTransacao.objects.get_or_create(
        pagamento=pagamento,
        defaults={
            "venda": venda,
            "filial": venda.filial,
            "terminal": terminal,
            "nsu_sitef": result.nsu_sitef,
            "nsu_host": result.nsu_host,
            "codigo_retorno": result.codigo_retorno,
            "mensagem_retorno": result.mensagem_retorno,
            "raw_request": result.raw_request,
            "raw_response": result.raw_response,
        },
    )

    # Se já existia, atualizamos campos relevantes
    if not _created:
        transacao.nsu_sitef = result.nsu_sitef
        transacao.nsu_host = result.nsu_host
        transacao.codigo_retorno = result.codigo_retorno
        transacao.mensagem_retorno = result.mensagem_retorno
        transacao.raw_request = result.raw_request
        transacao.raw_response = result.raw_response
        transacao.save(
            update_fields=[
                "nsu_sitef",
                "nsu_host",
                "codigo_retorno",
                "mensagem_retorno",
                "raw_request",
                "raw_response",
            ]
        )

    # Importante: o status do pagamento continua PENDENTE aqui.
    # Só o registrar_pagamento_service vai marcar AUTORIZADO/NEGADO depois.
    return pagamento
