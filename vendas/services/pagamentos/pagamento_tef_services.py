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

from vendas.services.pagamentos.iniciar_pagamento_service import iniciar_pagamento  # mantém o path

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
    - Garante que o terminal permite TEF (terminal.permite_tef == True).
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

    # NOVO: validação de terminal.permite_tef (requisito do sprint)
    if not getattr(terminal, "permite_tef", False):
        logger.info(
            "Tentativa de iniciar TEF em terminal que não permite TEF. venda_id=%s terminal_id=%s",
            venda.id,
            terminal.id,
        )
        raise ValidationError("O terminal informado não está habilitado para TEF.")

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

def registrar_auditoria_tef(*, pagamento, retorno):
    from django.apps import apps
    AuditoriaTef = apps.get_model("pagamentos", "AuditoriaTef")
    AuditoriaTef.objects.create(
        pagamento=pagamento,
        venda_id=pagamento.venda_id,
        tenant_id=pagamento.venda.tenant_id,
        raw=retorno
    )


def processar_retorno_tef(*, pagamento, retorno_tef):
    """
    Processa o retorno do TEF (DLL, socket, POS, ACI, PayGo etc.)
    e sincroniza com o modelo de Pagamento e Venda.

    retorno_tef deve conter:
      - status: 'APROVADO', 'NEGADO', 'PENDENTE', 'TIMEOUT', 'DUPLICADO'
      - nsu
      - autorizacao
      - bin
      - bandeira
      - via_cliente
      - via_estabelecimento
      - codigo_rede / mensagem / raw
    """
    from django.db import transaction
    from django.apps import apps

    Pagamento = apps.get_model("pagamentos", "Pagamento")
    Venda = apps.get_model("vendas", "Venda")

    from vendas.models.venda_models import VendaStatus

    if not isinstance(pagamento, Pagamento):
        raise TypeError("pagamento deve ser uma instância de Pagamento")

    with transaction.atomic():
        pagamento = Pagamento.objects.select_for_update().get(pk=pagamento.pk)
        venda = pagamento.venda

        status = (retorno_tef.get("status") or "").upper()

        if status == "APROVADO":
            pagamento.status = StatusPagamento.AUTORIZADO
            pagamento.nsu = retorno_tef.get("nsu")
            pagamento.codigo_autorizacao = retorno_tef.get("autorizacao")
            pagamento.via_cliente = retorno_tef.get("via_cliente")
            pagamento.via_estabelecimento = retorno_tef.get("via_estabelecimento")
            pagamento.bandeira = retorno_tef.get("bandeira")
            pagamento.raw_tef = retorno_tef

            # Venda só avança para pagamento confirmado SE TODOS os pagamentos forem aprovados
            if venda.tem_todos_pagamentos_confirmados():
                venda.status = VendaStatus.PAGAMENTO_CONFIRMADO

        elif status == "NEGADO":
            pagamento.status = StatusPagamento.NEGADO
            venda.status = VendaStatus.PAGAMENTO_NEGADO

        elif status in {"TIMEOUT", "PENDENTE"}:
            pagamento.status = StatusPagamento.PENDENTE
            venda.status = VendaStatus.PENDENTE_AUTORIZACAO

        elif status == "DUPLICADO":
            pagamento.status = StatusPagamento.AUTORIZADO  # confirmação idempotente

        else:
            pagamento.status = StatusPagamento.ERRO
            venda.status = VendaStatus.ERRO_PAGAMENTO

        pagamento.save()
        venda.save()

        # cria trilha auditável TEF (obrigatório por auditoria PCI)
        registrar_auditoria_tef(pagamento=pagamento, retorno=retorno_tef)

        return pagamento

