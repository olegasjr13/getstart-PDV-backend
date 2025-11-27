# vendas/tests/test_venda_multitenant.py

import logging
from decimal import Decimal

import pytest
from django.apps import apps
from django_tenants.utils import schema_context

from fiscal.models.ncm_models import NCM
from produtos.models.grupo_produtos_models import GrupoProduto
from produtos.models.unidade_medidas_models import UnidadeMedida
from vendas.models.venda_models import VendaStatus, TipoVenda, TipoDocumentoFiscal
from metodoPagamento.models.metodo_pagamento_models import MetodoPagamentoTipo

logger = logging.getLogger(__name__)


@pytest.mark.django_db(transaction=True)
def test_criar_venda_e_itens_em_um_tenant_nao_afeta_outro(two_tenants_with_admins):
    """
    Cenário:

    - Tenant1 e Tenant2 provisionados.
    - No tenant1:
        * Criar Filial/Terminal (já existem pela fixture).
        * Criar Venda (ABERTA).
        * Adicionar 2 itens.

    Verificamos:
    - A venda e os itens existem apenas no tenant1.
    - No tenant2 não há nenhuma venda/itens criados por esse fluxo.
    """
    schema1 = two_tenants_with_admins["schema1"]
    schema2 = two_tenants_with_admins["schema2"]

    FilialModel = apps.get_model("filial", "Filial")
    TerminalModel = apps.get_model("terminal", "Terminal")
    ProdutoModel = apps.get_model("produtos", "Produto")
    VendaModel = apps.get_model("vendas", "Venda")
    VendaItemModel = apps.get_model("vendas", "VendaItem")
    UserModel = apps.get_model("usuario", "User")

    # ---------------------------
    # Tenant1: criar venda e itens
    # ---------------------------
    with schema_context(schema1):
        filial = FilialModel.objects.first()
        assert filial is not None

        # Terminal simples para o teste
        terminal = TerminalModel.objects.create(
            filial=filial,
            identificador="CX01",
            ativo=True,
        )

        operador = UserModel.objects.first()
        assert operador is not None, "Pré-condição: deve haver ao menos 1 usuário."

        #cria grupo produto basico
        grupo_produto=GrupoProduto.objects.create(
            descricao="Grupo produto basico",
            ativo=True
        )

        # Criar ncm basico
        ncm = NCM.objects.create(
            descricao="NCM basico",
            codigo="87089990",
            ativo=True
        )

        # Criar unidade comercial e tributavel basica
        unidade=UnidadeMedida.objects.create(
            descricao="Unidade",
            sigla="UN",
            ativo=True
        )
        # Criar produtos básicos
        produto1 = ProdutoModel.objects.create(
            codigo_interno="123",
            descricao="Produto 1",
            preco_venda=Decimal("10.00"),
            grupo_id=grupo_produto.id,
            ncm_id=ncm.id,
            unidade_comercial_id=unidade.id,
            unidade_tributavel_id=unidade.id,
            ativo=True,
        )
        produto2 = ProdutoModel.objects.create(
            codigo_interno="456",
            descricao="Produto 2",
            grupo_id=grupo_produto.id,
            ncm_id=ncm.id,
            preco_venda=Decimal("5.50"),
            unidade_comercial_id=unidade.id,
            unidade_tributavel_id=unidade.id,    
            ativo=True,
        )

        venda = VendaModel.objects.create(
            filial=filial,
            terminal=terminal,
            operador=operador,
            tipo_venda=TipoVenda.VENDA_NORMAL,
            documento_fiscal_tipo=TipoDocumentoFiscal.NFCE,
            status=VendaStatus.ABERTA,
            total_bruto=Decimal("15.50"),
            total_desconto=Decimal("0.00"),
            total_liquido=Decimal("15.50"),
        )

        item1 = VendaItemModel.objects.create(
            venda=venda,
            produto=produto1,
            descricao=produto1.descricao,
            quantidade=Decimal("1.000"),
            preco_unitario=Decimal("10.000000"),
            total_bruto=Decimal("10.00"),
            desconto=Decimal("0.00"),
            total_liquido=Decimal("10.00"),
        )
        item2 = VendaItemModel.objects.create(
            venda=venda,
            produto=produto2,
            descricao=produto2.descricao,
            quantidade=Decimal("1.000"),
            preco_unitario=Decimal("5.500000"),
            total_bruto=Decimal("5.50"),
            desconto=Decimal("0.00"),
            total_liquido=Decimal("5.50"),
        )

        assert VendaModel.objects.count() == 1
        assert VendaItemModel.objects.count() == 2

    # ---------------------------
    # Tenant2: não deve haver vendas/itens criados por este fluxo
    # ---------------------------
    with schema_context(schema2):
        assert VendaModel.objects.count() == 0
        assert VendaItemModel.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_venda_permite_multiplos_pagamentos_e_isolamento_por_tenant(two_tenants_with_admins):
    """
    Cenário:

    - No tenant1:
        * Criar venda.
        * Criar dois métodos de pagamento (DINHEIRO, CRÉDITO).
        * Criar dois pagamentos para mesma venda (mix de métodos).
    - No tenant2:
        * Nenhuma venda criada.

    Verificamos:
    - Tenant1 possui 1 venda e 2 pagamentos.
    - Tenant2 não possui vendas/pagamentos.
    """
    schema1 = two_tenants_with_admins["schema1"]
    schema2 = two_tenants_with_admins["schema2"]

    FilialModel = apps.get_model("filial", "Filial")
    TerminalModel = apps.get_model("terminal", "Terminal")
    VendaModel = apps.get_model("vendas", "Venda")
    VendaPagamentoModel = apps.get_model("vendas", "VendaPagamento")
    MetodoPagamentoModel = apps.get_model("metodoPagamento", "MetodoPagamento")
    UserModel = apps.get_model("usuario", "User")

    # Tenant1
    with schema_context(schema1):
        filial = FilialModel.objects.first()
        terminal = TerminalModel.objects.create(
            filial=filial,
            identificador="CX02",
            ativo=True,
        )
        operador = UserModel.objects.first()

        venda = VendaModel.objects.create(
            filial=filial,
            terminal=terminal,
            operador=operador,
            tipo_venda=TipoVenda.VENDA_NORMAL,
            documento_fiscal_tipo=TipoDocumentoFiscal.NFCE,
            status=VendaStatus.AGUARDANDO_PAGAMENTO,
            total_bruto=Decimal("100.00"),
            total_desconto=Decimal("0.00"),
            total_liquido=Decimal("100.00"),
        )

        mp_din = MetodoPagamentoModel.objects.create(
            codigo="DIN_T1",
            tipo=MetodoPagamentoTipo.DINHEIRO,
            descricao="Dinheiro Tenant1",
            utiliza_tef=False,
            codigo_fiscal="01",
            codigo_tef=None,
            desconto_automatico_percentual=None,
            permite_parcelamento=False,
            max_parcelas=1,
            valor_minimo_parcela=None,
            permite_troco=True,
            ordem_exibicao=1,
            permite_desconto=True,
            ativo=True,
        )
        mp_cred = MetodoPagamentoModel.objects.create(
            codigo="CRC_T1",
            tipo=MetodoPagamentoTipo.CREDITO,
            descricao="Crédito Tenant1",
            utiliza_tef=True,
            codigo_fiscal="03",
            codigo_tef="CRED_T1",
            desconto_automatico_percentual=None,
            permite_parcelamento=True,
            max_parcelas=6,
            valor_minimo_parcela=Decimal("10.00"),
            permite_troco=False,
            ordem_exibicao=2,
            permite_desconto=True,
            ativo=True,
        )

        pg1 = VendaPagamentoModel.objects.create(
            venda=venda,
            metodo_pagamento=mp_din,
            valor=Decimal("40.00"),
            valor_troco=Decimal("0.00"),
            utiliza_tef=False,
            tef_status="NAO_APLICA",
        )
        pg2 = VendaPagamentoModel.objects.create(
            venda=venda,
            metodo_pagamento=mp_cred,
            valor=Decimal("60.00"),
            valor_troco=Decimal("0.00"),
            utiliza_tef=True,
            tef_status="APROVADO",
        )

        assert VendaModel.objects.count() == 1
        assert VendaPagamentoModel.objects.count() == 2

    # Tenant2
    with schema_context(schema2):
        VendaModel = apps.get_model("vendas", "Venda")
        VendaPagamentoModel = apps.get_model("vendas", "VendaPagamento")
        assert VendaModel.objects.count() == 0
        assert VendaPagamentoModel.objects.count() == 0
