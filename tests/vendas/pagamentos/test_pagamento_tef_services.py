# tests/vendas/pagamentos/test_pagamento_tef_services.py

import logging
from decimal import Decimal
from unittest.mock import Mock

import pytest
from django.apps import apps
from django.core.exceptions import ValidationError
from django_tenants.utils import schema_context

from vendas.models.venda_pagamentos_models import StatusPagamento
from vendas.models.venda_models import VendaStatus
from vendas.services.pagamentos.iniciar_pagamento_service import iniciar_pagamento, registrar_pagamento_service
from vendas.services.pagamentos.pagamento_tef_services import (
    iniciar_pagamento_tef_com_cliente,
)

from tef.clients.base import TefIniciarResult

logger = logging.getLogger(__name__)


@pytest.mark.django_db(transaction=True)
def test_iniciar_pagamento_tef_com_cliente_cria_pagamento_pendente_e_teftransacao(
    two_tenants_with_admins,
):
    """
    Cenário:
    - Venda normal com total_liquido = 100,00 e status ABERTA.
    - Método de pagamento configurado para TEF (utiliza_tef=True).
    - Cliente TEF (mock) retorna sucesso de comunicação com NSU.

    Esperado:
    - Criado VendaPagamento:
        * utiliza_tef = True
        * status = PENDENTE
        * valor_solicitado = 100,00
        * valor_autorizado = None
    - Criada TefTransacao ligada ao pagamento, com nsu_sitef / nsu_host preenchidos.
    - total_pago da venda permanece 0,00 (nenhuma autorização ainda).
    """
    schema1 = two_tenants_with_admins["schema1"]

    FilialModel = apps.get_model("filial", "Filial")
    TerminalModel = apps.get_model("terminal", "Terminal")
    UserModel = apps.get_model("usuario", "User")
    MetodoPagamentoModel = apps.get_model("metodoPagamento", "MetodoPagamento")
    VendaModel = apps.get_model("vendas", "Venda")
    TefTransacaoModel = apps.get_model("tef", "TefTransacao")

    with schema_context(schema1):
        filial = FilialModel.objects.first()
        operador = UserModel.objects.first()
        assert filial is not None
        assert operador is not None

        terminal = TerminalModel.objects.create(
            filial=filial,
            identificador="CX_TEF_01",
            ativo=True,
        )

        metodo_tef = MetodoPagamentoModel.objects.create(
            descricao="CRÉDITO TEF",
            tipo="CRC",  # ajuste conforme seu TextChoices
            utiliza_tef=True,
            permite_troco=False,
            codigo_fiscal="03",  # crédito à vista, por exemplo
            ativo=True,
        )

        venda = VendaModel.objects.create(
            filial=filial,
            terminal=terminal,
            operador=operador,
            tipo_venda="VENDA_NORMAL",
            documento_fiscal_tipo="NFCE",
            status=VendaStatus.ABERTA,
            total_bruto=Decimal("100.00"),
            total_desconto=Decimal("0.00"),
            total_liquido=Decimal("100.00"),
            total_pago=Decimal("0.00"),
            total_troco=Decimal("0.00"),
        )

        # Mock do cliente TEF
        nsu_sitef = "123456"
        nsu_host = "654321"

        class FakeTefClient:
            def iniciar_transacao(self, req):
                logger.info(
                    "FakeTefClient.iniciar_transacao chamado. pagamento_id=%s valor=%s",
                    req.pagamento.id,
                    req.valor,
                )
                # Podemos validar alguns campos do request
                assert req.valor == Decimal("100.00")
                assert req.terminal.id == terminal.id

                return TefIniciarResult(
                    sucesso_comunicacao=True,
                    nsu_sitef=nsu_sitef,
                    nsu_host=nsu_host,
                    codigo_retorno="00",
                    mensagem_retorno="TRANSACAO INICIADA",
                    raw_request="RAW_REQ",
                    raw_response="RAW_RESP",
                )

        tef_client = FakeTefClient()

        logger.info("Iniciando pagamento TEF com cliente fake.")
        pagamento = iniciar_pagamento_tef_com_cliente(
            venda=venda,
            metodo_pagamento=metodo_tef,
            valor=Decimal("100.00"),
            operador=operador,
            terminal=terminal,
            tef_client=tef_client,
        )

        venda.refresh_from_db()
        pagamento.refresh_from_db()

        assert pagamento.utiliza_tef is True
        assert pagamento.status == StatusPagamento.PENDENTE
        assert pagamento.valor_solicitado == Decimal("100.00")
        assert pagamento.valor_autorizado is None

        # Nenhuma alteração ainda nos totais da venda (somente na autorização)
        assert venda.total_pago == Decimal("0.00")

        transacoes = TefTransacaoModel.objects.filter(pagamento=pagamento)
        assert transacoes.count() == 1

        transacao = transacoes.first()
        assert transacao.nsu_sitef == nsu_sitef
        assert transacao.nsu_host == nsu_host

@pytest.mark.django_db(transaction=True)
def test_registrar_pagamento_service_autorizado_atualiza_totais_e_status(
    two_tenants_with_admins,
):
    """
    Cenário:
    - Venda de 100,00 com status ABERTA.
    - Pagamento TEF iniciado e PENDENTE.
    - registrar_pagamento_service chamado com autorizado=True, valor_confirmado=100,00.

    Esperado:
    - pagamento.status = AUTORIZADO.
    - pagamento.valor_autorizado = 100,00.
    - venda.total_pago = 100,00.
    - saldo_a_pagar <= 0.
    - venda.status = PAGAMENTO_CONFIRMADO.
    """
    schema1 = two_tenants_with_admins["schema1"]

    FilialModel = apps.get_model("filial", "Filial")
    TerminalModel = apps.get_model("terminal", "Terminal")
    UserModel = apps.get_model("usuario", "User")
    MetodoPagamentoModel = apps.get_model("metodoPagamento", "MetodoPagamento")
    VendaModel = apps.get_model("vendas", "Venda")

    with schema_context(schema1):
        filial = FilialModel.objects.first()
        operador = UserModel.objects.first()
        assert filial is not None
        assert operador is not None

        terminal = TerminalModel.objects.create(
            filial=filial,
            identificador="CX_TEF_02",
            ativo=True,
        )

        metodo_tef = MetodoPagamentoModel.objects.create(
            descricao="CRÉDITO TEF",
            tipo="CRC",
            utiliza_tef=True,
            permite_troco=False,
            codigo_fiscal="03",
            ativo=True,
        )

        venda = VendaModel.objects.create(
            filial=filial,
            terminal=terminal,
            operador=operador,
            tipo_venda="VENDA_NORMAL",
            documento_fiscal_tipo="NFCE",
            status=VendaStatus.ABERTA,
            total_bruto=Decimal("100.00"),
            total_desconto=Decimal("0.00"),
            total_liquido=Decimal("100.00"),
            total_pago=Decimal("0.00"),
            total_troco=Decimal("0.00"),
        )

        # Criar pagamento TEF pendente usando o próprio iniciar_pagamento (sem cliente TEF aqui)


        pagamento = iniciar_pagamento(
            venda=venda,
            metodo_pagamento=metodo_tef,
            valor=Decimal("100.00"),
            operador=operador,
            usar_tef=True,
        )

        venda.refresh_from_db()
        pagamento.refresh_from_db()

        assert pagamento.status == StatusPagamento.PENDENTE
        assert pagamento.utiliza_tef is True
        assert venda.total_pago == Decimal("0.00")

        nsu_sitef = "999001"
        nsu_host = "H001"

        logger.info("Registrando resultado TEF autorizado.")
        registrar_pagamento_service(
            pagamento=pagamento,
            autorizado=True,
            nsu_sitef=nsu_sitef,
            nsu_host=nsu_host,
            codigo_autorizacao="ABC123",
            codigo_retorno="00",
            mensagem_retorno="APROVADO",
            valor_confirmado=Decimal("100.00"),
            raw_request="RAW_REQ_AUTH",
            raw_response="RAW_RESP_AUTH",
        )

        venda.refresh_from_db()
        pagamento.refresh_from_db()

        assert pagamento.status == StatusPagamento.AUTORIZADO
        assert pagamento.valor_autorizado == Decimal("100.00")
        assert pagamento.nsu_sitef == nsu_sitef
        assert pagamento.nsu_host == nsu_host

        assert venda.total_pago == Decimal("100.00")
        assert venda.saldo_a_pagar <= 0
        assert venda.status == VendaStatus.PAGAMENTO_CONFIRMADO

@pytest.mark.django_db(transaction=True)
def test_registrar_pagamento_service_idempotente_quando_status_ja_nao_pendente(
    two_tenants_with_admins,
):
    """
    Cenário:
    - Pagamento TEF PENDENTE.
    - 1ª chamada registrar_pagamento_service => autorizado=True.
        * pagamento.status = AUTORIZADO.
        * venda.total_pago = 100,00.
    - 2ª chamada registrar_pagamento_service com os MESMOS dados/NSU.

    Esperado:
    - 2ª chamada tratada como idempotente:
        * pagamento.status continua AUTORIZADO.
        * venda.total_pago permanece o mesmo.
    """
    schema1 = two_tenants_with_admins["schema1"]

    FilialModel = apps.get_model("filial", "Filial")
    TerminalModel = apps.get_model("terminal", "Terminal")
    UserModel = apps.get_model("usuario", "User")
    MetodoPagamentoModel = apps.get_model("metodoPagamento", "MetodoPagamento")
    VendaModel = apps.get_model("vendas", "Venda")

    with schema_context(schema1):
        filial = FilialModel.objects.first()
        operador = UserModel.objects.first()
        assert filial is not None
        assert operador is not None

        terminal = TerminalModel.objects.create(
            filial=filial,
            identificador="CX_TEF_03",
            ativo=True,
        )

        metodo_tef = MetodoPagamentoModel.objects.create(
            descricao="CRÉDITO TEF",
            tipo="CRC",
            utiliza_tef=True,
            permite_troco=False,
            codigo_fiscal="03",
            ativo=True,
        )

        venda = VendaModel.objects.create(
            filial=filial,
            terminal=terminal,
            operador=operador,
            tipo_venda="VENDA_NORMAL",
            documento_fiscal_tipo="NFCE",
            status=VendaStatus.ABERTA,
            total_bruto=Decimal("100.00"),
            total_desconto=Decimal("0.00"),
            total_liquido=Decimal("100.00"),
            total_pago=Decimal("0.00"),
            total_troco=Decimal("0.00"),
        )


        pagamento = iniciar_pagamento(
            venda=venda,
            metodo_pagamento=metodo_tef,
            valor=Decimal("100.00"),
            operador=operador,
            usar_tef=True,
        )

        venda.refresh_from_db()
        pagamento.refresh_from_db()
        assert pagamento.status == StatusPagamento.PENDENTE

        nsu_sitef = "777001"
        nsu_host = "H777"

        # 1ª chamada: autoriza
        registrar_pagamento_service(
            pagamento=pagamento,
            autorizado=True,
            nsu_sitef=nsu_sitef,
            nsu_host=nsu_host,
            codigo_autorizacao="AUTH777",
            codigo_retorno="00",
            mensagem_retorno="APROVADO",
            valor_confirmado=Decimal("100.00"),
            raw_request="RAW_REQ_1",
            raw_response="RAW_RESP_1",
        )

        venda.refresh_from_db()
        pagamento.refresh_from_db()

        total_pago_apos_primeira = venda.total_pago
        status_apos_primeira = pagamento.status

        assert status_apos_primeira == StatusPagamento.AUTORIZADO
        assert total_pago_apos_primeira == Decimal("100.00")

        # 2ª chamada com mesmos dados -> deve ser idempotente
        registrar_pagamento_service(
            pagamento=pagamento,
            autorizado=True,
            nsu_sitef=nsu_sitef,
            nsu_host=nsu_host,
            codigo_autorizacao="AUTH777",
            codigo_retorno="00",
            mensagem_retorno="APROVADO",
            valor_confirmado=Decimal("100.00"),
            raw_request="RAW_REQ_2",
            raw_response="RAW_RESP_2",
        )

        venda.refresh_from_db()
        pagamento.refresh_from_db()

        assert pagamento.status == StatusPagamento.AUTORIZADO
        assert venda.total_pago == total_pago_apos_primeira
