# vendas/tests/pagamentos/test_pagamento_services.py

import logging
from decimal import Decimal

import pytest
from django.apps import apps
from django.core.exceptions import ValidationError
from django_tenants.utils import schema_context

from vendas.models.venda_models import VendaStatus
from vendas.services.pagamentos.validar_pagamento_service import (
    validar_pagamento_simples,
)
from vendas.services.pagamentos.iniciar_pagamento_service import iniciar_pagamento
from vendas.services.pagamentos.totais_pagamento_service import (
    recalcular_totais_pagamento,
)
from vendas.services.pagamentos.estornar_pagamento_service import (
    estornar_pagamento,
    estornar_pagamento_local,
)

# IMPORTAÇÃO CORRETA DO ENUM / TEXTCHOICES
from vendas.models.venda_pagamentos_models import StatusPagamento

logger = logging.getLogger(__name__)


@pytest.mark.django_db(transaction=True)
def test_validar_pagamento_valor_invalido(two_tenants_with_admins):
    """
    Cenário:
    - Tentar validar pagamento com valor <= 0.

    Esperado:
    - ValidationError com mensagem sobre valor inválido.
    """
    schema1 = two_tenants_with_admins["schema1"]

    VendaModel = apps.get_model("vendas", "Venda")
    FilialModel = apps.get_model("filial", "Filial")
    TerminalModel = apps.get_model("terminal", "Terminal")
    UserModel = apps.get_model("usuario", "User")
    MetodoPagamentoModel = apps.get_model("metodoPagamento", "MetodoPagamento")

    with schema_context(schema1):
        filial = FilialModel.objects.first()
        operador = UserModel.objects.first()
        terminal = TerminalModel.objects.create(
            filial=filial,
            identificador="CX_PAG_001",
            ativo=True,
        )

        metodo = MetodoPagamentoModel.objects.create(
            codigo="DIN",
            tipo="DIN",
            descricao="Dinheiro",
            utiliza_tef=False,
            codigo_fiscal="01",
            permite_troco=True,
            ativo=True,
        )

        venda = VendaModel.objects.create(
            filial=filial,
            terminal=terminal,
            operador=operador,
            status="ABERTA",
            total_bruto=Decimal("100.00"),
            total_desconto=Decimal("0.00"),
            total_liquido=Decimal("100.00"),
            total_pago=Decimal("0.00"),
            total_troco=Decimal("0.00"),
        )

        logger.info(
            "Validando pagamento com valor <= 0. Esperado: ValidationError."
        )

        with pytest.raises(ValidationError) as exc:
            validar_pagamento_simples(
                venda=venda,
                metodo_pagamento=metodo,
                valor=Decimal("0.00"),
            )

        logger.info("Erro recebido: %s", exc.value)
        assert "Valor do pagamento deve ser maior que zero." in str(exc.value)


@pytest.mark.django_db(transaction=True)
def test_validar_pagamento_venda_nao_aberta_para_pagamento(two_tenants_with_admins):
    """
    Cenário:
    - Venda com status CANCELADA.
    - Tentar validar pagamento.

    Esperado:
    - ValidationError indicando que a venda não permite pagamento.
    """
    schema1 = two_tenants_with_admins["schema1"]

    VendaModel = apps.get_model("vendas", "Venda")
    FilialModel = apps.get_model("filial", "Filial")
    TerminalModel = apps.get_model("terminal", "Terminal")
    UserModel = apps.get_model("usuario", "User")
    MetodoPagamentoModel = apps.get_model("metodoPagamento", "MetodoPagamento")

    with schema_context(schema1):
        filial = FilialModel.objects.first()
        operador = UserModel.objects.first()
        terminal = TerminalModel.objects.create(
            filial=filial,
            identificador="CX_PAG_002",
            ativo=True,
        )

        metodo = MetodoPagamentoModel.objects.create(
            codigo="DIN2",
            tipo="DIN",
            descricao="Dinheiro 2",
            utiliza_tef=False,
            codigo_fiscal="01",
            permite_troco=True,
            ativo=True,
        )

        venda = VendaModel.objects.create(
            filial=filial,
            terminal=terminal,
            operador=operador,
            status="CANCELADA",  # status que NÃO deveria permitir pagamento
            total_bruto=Decimal("100.00"),
            total_desconto=Decimal("0.00"),
            total_liquido=Decimal("100.00"),
            total_pago=Decimal("0.00"),
            total_troco=Decimal("0.00"),
        )

        logger.info(
            "Validando pagamento em venda CANCELADA. "
            "Esperado: ValidationError indicando que venda não permite pagamento."
        )

        with pytest.raises(ValidationError) as exc:
            validar_pagamento_simples(
                venda=venda,
                metodo_pagamento=metodo,
                valor=Decimal("50.00"),
            )

        logger.info("Erro recebido: %s", exc.value)
        assert "Venda não está em status que permita pagamento." in str(exc.value)


@pytest.mark.django_db(transaction=True)
def test_validar_pagamento_valor_maior_saldo_sem_troco(two_tenants_with_admins):
    """
    Cenário:
    - Venda com total_liquido=100, total_pago=0, total_troco=0.
    - Método de pagamento NÃO permite troco.
    - Tentar pagar 150.

    Esperado:
    - ValidationError informando que valor excede saldo e método não permite troco.
    """
    schema1 = two_tenants_with_admins["schema1"]

    VendaModel = apps.get_model("vendas", "Venda")
    FilialModel = apps.get_model("filial", "Filial")
    TerminalModel = apps.get_model("terminal", "Terminal")
    UserModel = apps.get_model("usuario", "User")
    MetodoPagamentoModel = apps.get_model("metodoPagamento", "MetodoPagamento")

    with schema_context(schema1):
        filial = FilialModel.objects.first()
        operador = UserModel.objects.first()
        terminal = TerminalModel.objects.create(
            filial=filial,
            identificador="CX_PAG_003",
            ativo=True,
        )

        metodo = MetodoPagamentoModel.objects.create(
            codigo="CRD01",
            tipo="CRD",
            descricao="Cartão de Débito",
            utiliza_tef=True,
            codigo_fiscal="04",
            permite_troco=False,
            ativo=True,
        )

        venda = VendaModel.objects.create(
            filial=filial,
            terminal=terminal,
            operador=operador,
            status="ABERTA",
            total_bruto=Decimal("100.00"),
            total_desconto=Decimal("0.00"),
            total_liquido=Decimal("100.00"),
            total_pago=Decimal("0.00"),
            total_troco=Decimal("0.00"),
        )

        logger.info(
            "Validando pagamento de 150 em venda com saldo 100, "
            "método sem troco. Esperado: ValidationError."
        )

        with pytest.raises(ValidationError) as exc:
            validar_pagamento_simples(
                venda=venda,
                metodo_pagamento=metodo,
                valor=Decimal("150.00"),
            )

        logger.info("Erro recebido: %s", exc.value)
        assert "Valor do pagamento excede o saldo a pagar" in str(exc.value)


@pytest.mark.django_db(transaction=True)
def test_validar_pagamento_valor_maior_saldo_com_troco(two_tenants_with_admins):
    """
    Cenário:
    - Venda com total_liquido=100, total_pago=0, total_troco=0.
    - Método de pagamento PERMITE troco (dinheiro).
    - Tentar pagar 150.

    Esperado:
    - NÃO deve levantar erro na validação (troco será tratado na criação do pagamento).
    """
    schema1 = two_tenants_with_admins["schema1"]

    VendaModel = apps.get_model("vendas", "Venda")
    FilialModel = apps.get_model("filial", "Filial")
    TerminalModel = apps.get_model("terminal", "Terminal")
    UserModel = apps.get_model("usuario", "User")
    MetodoPagamentoModel = apps.get_model("metodoPagamento", "MetodoPagamento")

    with schema_context(schema1):
        filial = FilialModel.objects.first()
        operador = UserModel.objects.first()
        terminal = TerminalModel.objects.create(
            filial=filial,
            identificador="CX_PAG_004",
            ativo=True,
        )

        metodo = MetodoPagamentoModel.objects.create(
            codigo="DIN3",
            tipo="DIN",
            descricao="Dinheiro 3",
            utiliza_tef=False,
            codigo_fiscal="01",
            permite_troco=True,
            ativo=True,
        )

        venda = VendaModel.objects.create(
            filial=filial,
            terminal=terminal,
            operador=operador,
            status="ABERTA",
            total_bruto=Decimal("100.00"),
            total_desconto=Decimal("0.00"),
            total_liquido=Decimal("100.00"),
            total_pago=Decimal("0.00"),
            total_troco=Decimal("0.00"),
        )

        logger.info(
            "Validando pagamento de 150 em venda com saldo 100, "
            "método COM troco. Esperado: validação OK (sem erro)."
        )

        validar_pagamento_simples(
            venda=venda,
            metodo_pagamento=metodo,
            valor=Decimal("150.00"),
        )

        logger.info("Validação concluída sem erros (como esperado).")


@pytest.mark.django_db(transaction=True)
def test_iniciar_pagamento_nao_tef_atualiza_totais_e_nao_usa_tef(two_tenants_with_admins):
    """
    Cenário:
    - Venda com total_liquido=100.
    - Método de pagamento NÃO utiliza TEF e permite troco=False.
    - Inicia pagamento de 100.

    Esperado:
    - Pagamento AUTORIZADO imediatamente.
    - utiliza_tef=False.
    - venda.total_pago=100, venda.total_troco=0.
    """
    schema1 = two_tenants_with_admins["schema1"]

    VendaModel = apps.get_model("vendas", "Venda")
    FilialModel = apps.get_model("filial", "Filial")
    TerminalModel = apps.get_model("terminal", "Terminal")
    UserModel = apps.get_model("usuario", "User")
    MetodoPagamentoModel = apps.get_model("metodoPagamento", "MetodoPagamento")

    with schema_context(schema1):
        filial = FilialModel.objects.first()
        operador = UserModel.objects.first()
        terminal = TerminalModel.objects.create(
            filial=filial,
            identificador="CX_PAG_005",
            ativo=True,
        )

        metodo = MetodoPagamentoModel.objects.create(
            codigo="DIN4",
            tipo="DIN",
            descricao="Dinheiro 4",
            utiliza_tef=False,
            codigo_fiscal="01",
            permite_troco=False,
            ativo=True,
        )

        venda = VendaModel.objects.create(
            filial=filial,
            terminal=terminal,
            operador=operador,
            status="ABERTA",
            total_bruto=Decimal("100.00"),
            total_desconto=Decimal("0.00"),
            total_liquido=Decimal("100.00"),
            total_pago=Decimal("0.00"),
            total_troco=Decimal("0.00"),
        )

        logger.info(
            "Iniciando pagamento NÃO TEF de 100 em venda com total_liquido=100."
        )

        pagamento = iniciar_pagamento(
            venda=venda,
            metodo_pagamento=metodo,
            valor=Decimal("100.00"),
            operador=operador,
            usar_tef=False,
        )

        venda.refresh_from_db()
        pagamento.refresh_from_db()

        assert pagamento.status == StatusPagamento.AUTORIZADO
        assert pagamento.utiliza_tef is False
        assert pagamento.valor_autorizado == Decimal("100.00")
        assert pagamento.valor_troco == Decimal("0.00")

        assert venda.total_pago == Decimal("100.00")
        assert venda.total_troco == Decimal("0.00")

        logger.info(
            "Pagamento autorizado e totais da venda atualizados corretamente. "
            "venda.total_pago=%s, venda.total_troco=%s",
            venda.total_pago,
            venda.total_troco,
        )


@pytest.mark.django_db(transaction=True)
def test_iniciar_pagamento_nao_tef_com_troco(two_tenants_with_admins):
    """
    Cenário:
    - Venda com total_liquido=100.
    - Método de pagamento NÃO TEF, permite troco=True.
    - Inicia pagamento de 150.

    Esperado:
    - Pagamento AUTORIZADO com valor_autorizado=100 e troco=50.
    - venda.total_pago=100, venda.total_troco=50.
    """
    schema1 = two_tenants_with_admins["schema1"]

    VendaModel = apps.get_model("vendas", "Venda")
    FilialModel = apps.get_model("filial", "Filial")
    TerminalModel = apps.get_model("terminal", "Terminal")
    UserModel = apps.get_model("usuario", "User")
    MetodoPagamentoModel = apps.get_model("metodoPagamento", "MetodoPagamento")

    with schema_context(schema1):
        filial = FilialModel.objects.first()
        operador = UserModel.objects.first()
        terminal = TerminalModel.objects.create(
            filial=filial,
            identificador="CX_PAG_006",
            ativo=True,
        )

        metodo = MetodoPagamentoModel.objects.create(
            codigo="DIN5",
            tipo="DIN",
            descricao="Dinheiro 5",
            utiliza_tef=False,
            codigo_fiscal="01",
            permite_troco=True,
            ativo=True,
        )

        venda = VendaModel.objects.create(
            filial=filial,
            terminal=terminal,
            operador=operador,
            status="ABERTA",
            total_bruto=Decimal("100.00"),
            total_desconto=Decimal("0.00"),
            total_liquido=Decimal("100.00"),
            total_pago=Decimal("0.00"),
            total_troco=Decimal("0.00"),
        )

        logger.info(
            "Iniciando pagamento NÃO TEF de 150 em venda com total_liquido=100 "
            "(esperado troco=50)."
        )

        pagamento = iniciar_pagamento(
            venda=venda,
            metodo_pagamento=metodo,
            valor=Decimal("150.00"),
            operador=operador,
            usar_tef=False,
        )

        venda.refresh_from_db()
        pagamento.refresh_from_db()

        assert pagamento.status == StatusPagamento.AUTORIZADO
        assert pagamento.utiliza_tef is False
        assert pagamento.valor_autorizado == Decimal("100.00")
        assert pagamento.valor_troco == Decimal("50.00")

        assert venda.total_pago == Decimal("100.00")
        assert venda.total_troco == Decimal("50.00")

        logger.info(
            "Pagamento com troco processado corretamente. "
            "venda.total_pago=%s, venda.total_troco=%s",
            venda.total_pago,
            venda.total_troco,
        )


@pytest.mark.django_db(transaction=True)
def test_iniciar_pagamento_tef_cria_pendente_e_nao_altera_totais(two_tenants_with_admins):
    """
    Cenário:
    - Venda com total_liquido=100.
    - Método de pagamento utiliza_tef=True.
    - Inicia pagamento TEF de 100.

    Esperado:
    - Pagamento PENDENTE, utiliza_tef=True.
    - Nenhuma alteração em venda.total_pago / total_troco.
    """
    schema1 = two_tenants_with_admins["schema1"]

    VendaModel = apps.get_model("vendas", "Venda")
    FilialModel = apps.get_model("filial", "Filial")
    TerminalModel = apps.get_model("terminal", "Terminal")
    UserModel = apps.get_model("usuario", "User")
    MetodoPagamentoModel = apps.get_model("metodoPagamento", "MetodoPagamento")

    with schema_context(schema1):
        filial = FilialModel.objects.first()
        operador = UserModel.objects.first()
        terminal = TerminalModel.objects.create(
            filial=filial,
            identificador="CX_PAG_007",
            ativo=True,
        )

        metodo = MetodoPagamentoModel.objects.create(
            codigo="CRDTEF",
            tipo="CRD",
            descricao="Cartão Crédito TEF",
            utiliza_tef=True,
            codigo_fiscal="03",
            permite_troco=False,
            ativo=True,
        )

        venda = VendaModel.objects.create(
            filial=filial,
            terminal=terminal,
            operador=operador,
            status="ABERTA",
            total_bruto=Decimal("100.00"),
            total_desconto=Decimal("0.00"),
            total_liquido=Decimal("100.00"),
            total_pago=Decimal("0.00"),
            total_troco=Decimal("0.00"),
        )

        logger.info(
            "Iniciando pagamento TEF de 100. Esperado: pagamento PENDENTE, "
            "utiliza_tef=True e totais da venda inalterados."
        )

        pagamento = iniciar_pagamento(
            venda=venda,
            metodo_pagamento=metodo,
            valor=Decimal("100.00"),
            operador=operador,
            usar_tef=True,
        )

        venda.refresh_from_db()
        pagamento.refresh_from_db()

        assert pagamento.status == StatusPagamento.PENDENTE
        assert pagamento.utiliza_tef is True
        assert pagamento.valor_autorizado is None
        assert pagamento.valor_troco == Decimal("0.00")

        assert venda.total_pago == Decimal("0.00")
        assert venda.total_troco == Decimal("0.00")

        logger.info(
            "Pagamento TEF iniciado corretamente. venda.total_pago=%s, venda.total_troco=%s",
            venda.total_pago,
            venda.total_troco,
        )


@pytest.mark.django_db(transaction=True)
def test_recalcular_totais_pagamento_considera_somente_autorizados(two_tenants_with_admins):
    """
    Cenário:
    - Venda com vários pagamentos:
        * p1 AUTORIZADO: 100, troco 0
        * p2 PENDENTE: 50
        * p3 ESTORNADO: 80
    - Executar recalcular_totais_pagamento.

    Esperado:
    - total_pago considera apenas pagamentos AUTORIZADOS.
    - total_troco soma apenas trocos de AUTORIZADOS.
    """
    schema1 = two_tenants_with_admins["schema1"]

    VendaModel = apps.get_model("vendas", "Venda")
    VendaPagamentoModel = apps.get_model("vendas", "VendaPagamento")
    FilialModel = apps.get_model("filial", "Filial")
    TerminalModel = apps.get_model("terminal", "Terminal")
    UserModel = apps.get_model("usuario", "User")
    MetodoPagamentoModel = apps.get_model("metodoPagamento", "MetodoPagamento")

    with schema_context(schema1):
        filial = FilialModel.objects.first()
        operador = UserModel.objects.first()
        terminal = TerminalModel.objects.create(
            filial=filial,
            identificador="CX_PAG_008",
            ativo=True,
        )

        metodo = MetodoPagamentoModel.objects.create(
            codigo="DIN6",
            tipo="DIN",
            descricao="Dinheiro 6",
            utiliza_tef=False,
            codigo_fiscal="01",
            permite_troco=True,
            ativo=True,
        )

        venda = VendaModel.objects.create(
            filial=filial,
            terminal=terminal,
            operador=operador,
            status="ABERTA",
            total_bruto=Decimal("300.00"),
            total_desconto=Decimal("0.00"),
            total_liquido=Decimal("300.00"),
            total_pago=Decimal("0.00"),
            total_troco=Decimal("0.00"),
        )

        logger.info("Criando pagamentos com status variados para teste de totais.")

        p1 = VendaPagamentoModel.objects.create(
            venda=venda,
            metodo_pagamento=metodo,
            valor_solicitado=Decimal("100.00"),
            valor_autorizado=Decimal("100.00"),
            valor_troco=Decimal("0.00"),
            status=StatusPagamento.AUTORIZADO,
            utiliza_tef=False,
        )

        p2 = VendaPagamentoModel.objects.create(
            venda=venda,
            metodo_pagamento=metodo,
            valor_solicitado=Decimal("50.00"),
            valor_autorizado=None,
            valor_troco=Decimal("0.00"),
            status=StatusPagamento.PENDENTE,
            utiliza_tef=False,
        )

        p3 = VendaPagamentoModel.objects.create(
            venda=venda,
            metodo_pagamento=metodo,
            valor_solicitado=Decimal("80.00"),
            valor_autorizado=Decimal("80.00"),
            valor_troco=Decimal("0.00"),
            status=StatusPagamento.ESTORNADO,
            utiliza_tef=False,
        )

        logger.info(
            "Recalculando totais de pagamento. Esperado: considerar somente AUTORIZADOS."
        )

        recalcular_totais_pagamento(venda=venda)

        venda.refresh_from_db()

        assert venda.total_pago == Decimal("100.00")
        assert venda.total_troco == Decimal("0.00")

        logger.info(
            "Totais recalculados: total_pago=%s, total_troco=%s",
            venda.total_pago,
            venda.total_troco,
        )

@pytest.mark.django_db(transaction=True)
def test_primeiro_pagamento_muda_status_para_aguardando_pagamento(two_tenants_with_admins):
    """
    Cenário:
    - Venda com total_liquido = 100,00 e status ABERTA.
    - Inicia pagamento NÃO TEF de 50,00 (ex.: dinheiro).

    Esperado:
    - pagamento AUTORIZADO.
    - total_pago = 50,00.
    - saldo_a_pagar > 0.
    - status da venda muda para AGUARDANDO_PAGAMENTO.
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

        terminal = TerminalModel.objects.create(
            filial=filial,
            identificador="CX_STATUS_PG_01",
            ativo=True,
        )

        metodo_dinheiro = MetodoPagamentoModel.objects.create(
            descricao="DINHEIRO",
            tipo="DIN",
            utiliza_tef=False,
            permite_troco=True,
            codigo_fiscal="01",
            ativo=True,
        )

        venda = VendaModel.objects.create(
            filial=filial,
            terminal=terminal,
            operador=operador,
            tipo_venda=VendaStatus.VENDA_NORMAL if hasattr(VendaStatus, "VENDA_NORMAL") else "VENDA_NORMAL",
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
            metodo_pagamento=metodo_dinheiro,
            valor=Decimal("50.00"),
            operador=operador,
        )

        venda.refresh_from_db()

        assert pagamento.status == StatusPagamento.AUTORIZADO
        assert venda.total_pago == Decimal("50.00")
        assert venda.saldo_a_pagar > 0
        assert venda.status == VendaStatus.AGUARDANDO_PAGAMENTO

@pytest.mark.django_db(transaction=True)
def test_venda_totalmente_paga_muda_status_para_pagamento_confirmado(two_tenants_with_admins):
    """
    Cenário:
    - Venda com total_liquido = 100,00 e status ABERTA.
    - 1º pagamento: 40,00 (status AGUARDANDO_PAGAMENTO).
    - 2º pagamento: 60,00 (fecha a venda).

    Esperado:
    - total_pago = 100,00.
    - saldo_a_pagar <= 0.
    - status da venda = PAGAMENTO_CONFIRMADO.
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

        terminal = TerminalModel.objects.create(
            filial=filial,
            identificador="CX_STATUS_PG_02",
            ativo=True,
        )

        metodo_dinheiro = MetodoPagamentoModel.objects.create(
            descricao="DINHEIRO",
            tipo="DIN",
            utiliza_tef=False,
            permite_troco=True,
            codigo_fiscal="01",
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

        iniciar_pagamento(
            venda=venda,
            metodo_pagamento=metodo_dinheiro,
            valor=Decimal("40.00"),
            operador=operador,
        )
        venda.refresh_from_db()
        assert venda.status == VendaStatus.AGUARDANDO_PAGAMENTO

        iniciar_pagamento(
            venda=venda,
            metodo_pagamento=metodo_dinheiro,
            valor=Decimal("60.00"),
            operador=operador,
        )
        venda.refresh_from_db()

        assert venda.total_pago == Decimal("100.00")
        assert venda.saldo_a_pagar <= 0
        assert venda.status == VendaStatus.PAGAMENTO_CONFIRMADO

@pytest.mark.django_db(transaction=True)
def test_estornar_pagamento_local_sem_senha_quando_terminal_nao_solicita(two_tenants_with_admins):
    """
    Cenário:
    - Terminal com solicitar_senha_estorno = False.
    - Pagamento local (não TEF) AUTORIZADO.
    - Operador chama estornar_pagamento_local sem aprovador.

    Esperado:
    - Estorno permitido.
    - Status do pagamento = ESTORNADO.
    - Totais da venda atualizados.
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

        terminal = TerminalModel.objects.create(
            filial=filial,
            identificador="CX_ESTORNO_01",
            ativo=True,
            solicitar_senha_estorno=False,
        )

        metodo_dinheiro = MetodoPagamentoModel.objects.create(
            descricao="DINHEIRO",
            tipo="DIN",
            utiliza_tef=False,
            permite_troco=True,
            codigo_fiscal="01",
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
            metodo_pagamento=metodo_dinheiro,
            valor=Decimal("100.00"),
            operador=operador,
        )
        venda.refresh_from_db()

        assert pagamento.status == StatusPagamento.AUTORIZADO
        assert venda.total_pago == Decimal("100.00")

        estornar_pagamento_local(
            pagamento=pagamento,
            operador=operador,
            motivo="Cliente desistiu do produto.",
        )

        pagamento.refresh_from_db()
        venda.refresh_from_db()

        assert pagamento.status == StatusPagamento.ESTORNADO
        assert venda.total_pago == Decimal("0.00")

@pytest.mark.django_db(transaction=True)
def test_estornar_pagamento_local_requer_aprovador_quando_terminal_solicita(two_tenants_with_admins):
    """
    Cenário:
    - Terminal com solicitar_senha_estorno = True.
    - Pagamento local AUTORIZADO.
    - Operador tenta estornar sem aprovador -> ValidationError.
    - Depois tenta com aprovador diferente -> estorno permitido.
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

        aprovador = UserModel.objects.create(
            username="supervisor_estorno",
            email="supervisor_estorno@localhost",
        )

        terminal = TerminalModel.objects.create(
            filial=filial,
            identificador="CX_ESTORNO_02",
            ativo=True,
            solicitar_senha_estorno=True,
        )

        metodo_dinheiro = MetodoPagamentoModel.objects.create(
            descricao="DINHEIRO",
            tipo="DIN",
            utiliza_tef=False,
            permite_troco=True,
            codigo_fiscal="01",
            ativo=True,
        )

        venda = VendaModel.objects.create(
            filial=filial,
            terminal=terminal,
            operador=operador,
            tipo_venda="VENDA_NORMAL",
            documento_fiscal_tipo="NFCE",
            status=VendaStatus.ABERTA,
            total_bruto=Decimal("50.00"),
            total_desconto=Decimal("0.00"),
            total_liquido=Decimal("50.00"),
            total_pago=Decimal("0.00"),
            total_troco=Decimal("0.00"),
        )

        pagamento = iniciar_pagamento(
            venda=venda,
            metodo_pagamento=metodo_dinheiro,
            valor=Decimal("50.00"),
            operador=operador,
        )
        venda.refresh_from_db()
        assert pagamento.status == StatusPagamento.AUTORIZADO

        # Tentativa sem aprovador -> erro
        with pytest.raises(ValidationError):
            estornar_pagamento_local(
                pagamento=pagamento,
                operador=operador,
                motivo="Erro de preço.",
            )

        # Tentativa com aprovador diferente -> sucesso
        estornar_pagamento_local(
            pagamento=pagamento,
            operador=operador,
            motivo="Erro de preço.",
            aprovador=aprovador,
        )

        pagamento.refresh_from_db()
        assert pagamento.status == StatusPagamento.ESTORNADO
