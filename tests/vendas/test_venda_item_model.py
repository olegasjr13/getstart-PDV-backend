# tests/vendas/test_venda_item_model.py

import logging
from decimal import Decimal

import pytest
from django.apps import apps
from django.core.exceptions import ValidationError
from django_tenants.utils import schema_context

logger = logging.getLogger(__name__)

pytestmark = pytest.mark.django_db(transaction=True)


def _bootstrap_produto(schema_name: str):
    """
    Cria grupo, unidade, NCM e produto mínimos para testar VendaItem
    dentro de um schema específico.
    """
    GrupoProduto = apps.get_model("produtos", "GrupoProduto")
    UnidadeMedida = apps.get_model("produtos", "UnidadeMedida")
    NCM = apps.get_model("fiscal", "NCM")
    Produto = apps.get_model("produtos", "Produto")

    with schema_context(schema_name):
        grupo = GrupoProduto.objects.create(
            nome="Grupo Teste",
            descricao="Grupo de produtos de teste",
            ativo=True,
        )
        un = UnidadeMedida.objects.create(
            sigla="UN",
            descricao="Unidade",
            fator_conversao=Decimal("1.000000"),
        )
        ncm = NCM.objects.create(
            codigo="22030000",
            descricao="Bebidas teste",
        )
        produto = Produto.objects.create(
            codigo_interno="PROD_ITEM",
            descricao="Produto para VendaItem",
            grupo=grupo,
            unidade_comercial=un,
            unidade_tributavel=un,
            fator_conversao_tributavel=Decimal("1.000000"),
            preco_venda=Decimal("10.000"),
            aliquota_icms=Decimal("18.00"),
            aliquota_pis=Decimal("1.65"),
            aliquota_cofins=Decimal("7.60"),
            desconto_maximo_percentual=Decimal("10.00"),
            ativo=True,
            ncm=ncm,
        )

    return {"produto": produto}


def _build_venda_item_basico(schema_name: str, produto, **overrides):
    """
    Monta uma instância de VendaItem (NÃO salva) com valores básicos.
    Vamos chamar apenas .clean(), sem full_clean(), para focar nas
    regras específicas de VendaItem.
    """
    VendaItem = apps.get_model("vendas", "VendaItem")

    defaults = dict(
        venda=None,  # não precisamos da venda para os testes de clean específicos
        produto=produto,
        descricao=produto.descricao,
        quantidade=Decimal("1.000"),
        preco_unitario=Decimal("10.000000"),
        total_bruto=Decimal("10.00"),
        desconto=Decimal("0.00"),
        total_liquido=Decimal("10.00"),
        percentual_desconto_aplicado=None,
        motivo_desconto=None,
        desconto_aprovado_por=None,
        ncm_codigo="22030000",
    )
    defaults.update(overrides)

    with schema_context(schema_name):
        return VendaItem(**defaults)


def test_venda_item_desconto_sem_motivo_dispara_erro(two_tenants_with_admins):
    """
    Cenário:
    - Item com desconto > 0 e motivo_desconto ausente.
    Expectativa:
    - clean() deve apontar erro em 'motivo_desconto'.
    """
    schema1 = two_tenants_with_admins["schema1"]
    logger.info(
        "Iniciando teste: desconto > 0 sem motivo_desconto deve falhar (schema=%s).",
        schema1,
    )

    ctx = _bootstrap_produto(schema1)
    produto = ctx["produto"]

    item = _build_venda_item_basico(
        schema1,
        produto,
        desconto=Decimal("2.00"),
        total_liquido=Decimal("8.00"),
        motivo_desconto=None,
    )

    with pytest.raises(ValidationError) as exc:
        item.clean()

    assert "motivo_desconto" in exc.value.message_dict
    logger.info("Teste concluído: motivo_desconto obrigatório quando há desconto.")


def test_venda_item_desconto_acima_limite_sem_aprovador_dispara_erro(
    two_tenants_with_admins,
):
    """
    Cenário:
    - Produto com desconto_maximo_percentual = 10%.
    - Item com percentual_desconto_aplicado = 15%, sem desconto_aprovado_por.
    Expectativa:
    - clean() deve apontar erro em 'percentual_desconto_aplicado'.
    """
    schema1 = two_tenants_with_admins["schema1"]
    logger.info(
        "Iniciando teste: desconto acima do limite sem aprovador deve falhar (schema=%s).",
        schema1,
    )

    ctx = _bootstrap_produto(schema1)
    produto = ctx["produto"]

    item = _build_venda_item_basico(
        schema1,
        produto,
        percentual_desconto_aplicado=Decimal("15.00"),
        desconto=Decimal("1.50"),
        total_liquido=Decimal("8.50"),
    )

    with pytest.raises(ValidationError) as exc:
        item.clean()

    assert "percentual_desconto_aplicado" in exc.value.message_dict
    logger.info(
        "Teste concluído: validação de limite de desconto vs produto funcionando."
    )


def test_venda_item_desconto_acima_limite_com_aprovador_eh_aceito(
    two_tenants_with_admins,
):
    """
    Cenário:
    - Produto com desconto_maximo_percentual = 10%.
    - Item com 15% de desconto, mas com desconto_aprovado_por informado.
    Expectativa:
    - clean() deve aceitar (não lançar ValidationError nesse ponto).
    """
    schema1 = two_tenants_with_admins["schema1"]
    logger.info(
        "Iniciando teste: desconto acima do limite COM aprovador deve ser aceito (schema=%s).",
        schema1,
    )

    ctx = _bootstrap_produto(schema1)
    produto = ctx["produto"]

    User = apps.get_model("usuario", "User")
    with schema_context(schema1):
        aprovador = User()  # não precisamos salvar para o clean() do item

    item = _build_venda_item_basico(
        schema1,
        produto,
        percentual_desconto_aplicado=Decimal("15.00"),
        desconto=Decimal("1.50"),
        total_liquido=Decimal("8.50"),
        desconto_aprovado_por=aprovador,
        motivo_desconto="Motivo qualquer",
    )

    # Não deve lançar ValidationError por causa do limite de desconto
    item.clean()
    logger.info(
        "Teste concluído: item com desconto acima do limite, mas aprovado, foi validado com sucesso."
    )


def test_venda_item_snapshot_fiscal_preenchido_a_partir_do_produto(
    two_tenants_with_admins,
):
    """
    Cenário:
    - Produto com NCM e dois CESTs ativos (códigos diferentes).
    - Chamada de preencher_a_partir_do_produto(produto) no item.
    Expectativa:
    - ncm_codigo, origem_mercadoria_item, cfop_aplicado, csosn/cst/aliquotas preenchidos.
    - cest_codigo definido com o CEST de menor código.
    """
    schema1 = two_tenants_with_admins["schema1"]
    logger.info(
        "Iniciando teste: snapshot fiscal do item a partir do produto (schema=%s).",
        schema1,
    )

    CEST = apps.get_model("fiscal", "CEST")
    NCM = apps.get_model("fiscal", "NCM")
    Produto = apps.get_model("produtos", "Produto")
    GrupoProduto = apps.get_model("produtos", "GrupoProduto")
    UnidadeMedida = apps.get_model("produtos", "UnidadeMedida")

    with schema_context(schema1):
        grupo = GrupoProduto.objects.create(
            nome="Grupo Snapshot",
            descricao="Grupo para snapshot",
            ativo=True,
        )
        un = UnidadeMedida.objects.create(
            sigla="UN",
            descricao="Unidade",
            fator_conversao=Decimal("1.000000"),
        )
        ncm = NCM.objects.create(
            codigo="22030002",
            descricao="NCM com múltiplos CEST",
        )
        cest1 = CEST.objects.create(
            codigo="1234567", descricao="CEST maior", ativo=True
        )
        cest2 = CEST.objects.create(
            codigo="0123456", descricao="CEST menor", ativo=True
        )
        ncm.cests.add(cest1, cest2)

        produto = Produto.objects.create(
            codigo_interno="PROD_SNAPSHOT",
            descricao="Produto Snapshot",
            grupo=grupo,
            unidade_comercial=un,
            unidade_tributavel=un,
            fator_conversao_tributavel=Decimal("1.000000"),
            preco_venda=Decimal("50.000"),
            aliquota_icms=Decimal("18.00"),
            aliquota_pis=Decimal("1.65"),
            aliquota_cofins=Decimal("7.60"),
            csosn_icms="102",
            cst_pis="01",
            cst_cofins="01",
            cst_ipi="50",
            ativo=True,
            ncm=ncm,
        )

        VendaItem = apps.get_model("vendas", "VendaItem")
        item = VendaItem(
            venda=None,
            produto=produto,
            descricao="",
            quantidade=Decimal("1.000"),
            preco_unitario=Decimal("50.000000"),
            total_bruto=Decimal("50.00"),
            desconto=Decimal("0.00"),
            total_liquido=Decimal("50.00"),
        )

        item.preencher_a_partir_do_produto(produto)

    assert item.ncm_codigo == "22030002"
    assert item.origem_mercadoria_item == produto.origem_mercadoria
    assert item.cfop_aplicado == produto.cfop_venda_dentro_estado
    assert item.csosn_icms_item == "102"
    assert item.cst_pis_item == "01"
    assert item.cst_cofins_item == "01"
    assert item.cst_ipi_item == "50"
    assert item.cest_codigo == "0123456"

    logger.info(
        "Teste concluído: snapshot fiscal do item a partir do produto preenchido corretamente."
    )


def test_venda_item_recalcular_totais_usa_percentual_desconto(
    two_tenants_with_admins,
):
    """
    Cenário:
    - Item com quantidade=2, preco_unitario=10, percentual_desconto_aplicado=10%.
    Expectativa:
    - total_bruto = 20, desconto = 2, total_liquido = 18.
    """
    schema1 = two_tenants_with_admins["schema1"]
    logger.info(
        "Iniciando teste: recalcular_totais com percentual de desconto (schema=%s).",
        schema1,
    )

    ctx = _bootstrap_produto(schema1)
    produto = ctx["produto"]

    item = _build_venda_item_basico(
        schema1,
        produto,
        quantidade=Decimal("2.000"),
        preco_unitario=Decimal("10.000000"),
        total_bruto=Decimal("0.00"),   # será recalculado
        desconto=Decimal("0.00"),
        total_liquido=Decimal("0.00"),
        percentual_desconto_aplicado=Decimal("10.00"),
    )

    item.recalcular_totais()

    assert item.total_bruto == Decimal("20.00")
    assert item.desconto == Decimal("2.00")
    assert item.total_liquido == Decimal("18.00")

    logger.info(
        "Teste concluído: recalcular_totais aplicou corretamente o percentual de desconto."
    )
