# tef/tests/test_tef_transacao_multitenant.py

import logging
from decimal import Decimal

import pytest
from django.apps import apps
from django_tenants.utils import schema_context

from tef.models.tef_models import TefProvider, TefTransacao, TefTransacaoStatus
from vendas.models.venda_models import VendaStatus, TipoVenda, TipoDocumentoFiscal
from metodoPagamento.models.metodo_pagamento_models import MetodoPagamentoTipo

logger = logging.getLogger(__name__)


@pytest.mark.django_db(transaction=True)
def test_tef_transacao_vinculada_a_pagamento_e_isolada_entre_tenants(
    two_tenants_with_admins,
):
    """
    Cenário:

    - Tenant1:
        * Criar venda + pagamento usando método que utiliza TEF.
        * Criar TefTransacao APROVADA.
    - Tenant2:
        * Não criar nada.

    Verificamos:
    - Tenant1 possui 1 TefTransacao vinculada ao pagamento.
    - Tenant2 não possui TefTransacao.
    """
    schema1 = two_tenants_with_admins["schema1"]
    schema2 = two_tenants_with_admins["schema2"]

    FilialModel = apps.get_model("filial", "Filial")
    TerminalModel = apps.get_model("terminal", "Terminal")
    UserModel = apps.get_model("usuario", "User")
    MetodoPagamentoModel = apps.get_model("metodoPagamento", "MetodoPagamento")
    VendaModel = apps.get_model("vendas", "Venda")
    VendaPagamentoModel = apps.get_model("vendas", "VendaPagamento")

    # Tenant1
    with schema_context(schema1):
        filial = FilialModel.objects.first()
        terminal = TerminalModel.objects.create(
            filial=filial,
            identificador="CX03",
            ativo=True,
        )
        operador = UserModel.objects.first()

        venda = VendaModel.objects.create(
            filial=filial,
            terminal=terminal,
            operador=operador,
            tipo_venda=TipoVenda.VENDA_NORMAL,
            documento_fiscal_tipo=TipoDocumentoFiscal.NFCE,
            status=VendaStatus.PAGAMENTO_EM_PROCESSAMENTO,
            total_bruto=Decimal("50.00"),
            total_desconto=Decimal("0.00"),
            total_liquido=Decimal("50.00"),
        )

        mp_cred = MetodoPagamentoModel.objects.create(
            codigo="CRC_TEF",
            tipo=MetodoPagamentoTipo.CREDITO,
            descricao="Crédito TEF",
            utiliza_tef=True,
            codigo_fiscal="03",
            codigo_tef="CRED_TEF",
            desconto_automatico_percentual=None,
            permite_parcelamento=True,
            max_parcelas=3,
            valor_minimo_parcela=Decimal("10.00"),
            permite_troco=False,
            ordem_exibicao=1,
            permite_desconto=True,
            ativo=True,
        )

        pagamento = VendaPagamentoModel.objects.create(
            venda=venda,
            metodo_pagamento=mp_cred,
            valor=Decimal("50.00"),
            valor_troco=Decimal("0.00"),
            utiliza_tef=True,
            tef_status=None,
        )

        tef = TefTransacao.objects.create(
            pagamento=pagamento,
            provider=TefProvider.SITEF,
            status=TefTransacaoStatus.APROVADA,
            nsu_host="123456",
            codigo_autorizacao="AUTH001",
            bandeira="VISA",
            modalidade="Crédito",
            parcelas=1,
            valor_transacao=Decimal("50.00"),
            pan_mascarado="**** **** **** 1234",
            codigo_retorno="00",
            mensagem_retorno="Transação aprovada",
        )

        assert TefTransacao.objects.count() == 1
        assert tef.pagamento_id == pagamento.id

    # Tenant2
    with schema_context(schema2):
        assert TefTransacao.objects.count() == 0
