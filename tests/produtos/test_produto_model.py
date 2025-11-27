# produtos/tests/test_produto_model.py

import logging
from decimal import Decimal

import pytest
from django.apps import apps
from django.core.exceptions import ValidationError
from django_tenants.utils import schema_context

logger = logging.getLogger(__name__)

# Segue o padrão dos testes multitenant existentes (terminal, fiscal/ncm etc.)
pytestmark = pytest.mark.django_db(transaction=True)


def _bootstrap_context(schema_name: str):
    """
    Cria as entidades básicas necessárias para testar o model Produto
    dentro de um schema específico (tenant).
    """
    GrupoProduto = apps.get_model("produtos", "GrupoProduto")
    UnidadeMedida = apps.get_model("produtos", "UnidadeMedida")
    NCM = apps.get_model("fiscal", "NCM")

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

    return {"grupo": grupo, "un": un, "ncm": ncm}


def _build_produto(schema_name: str, grupo, un, ncm=None, **overrides):
    """
    Monta uma instância de Produto (ainda não salva) para o schema informado.
    """
    Produto = apps.get_model("produtos", "Produto")

    defaults = dict(
        codigo_interno="PROD_TESTE",
        descricao="Produto de teste",
        grupo=grupo,
        unidade_comercial=un,
        unidade_tributavel=un,
        fator_conversao_tributavel=Decimal("1.000000"),
        preco_venda=Decimal("10.000"),
        aliquota_icms=Decimal("0.00"),
        aliquota_pis=Decimal("0.00"),
        aliquota_cofins=Decimal("0.00"),
        ativo=True,
    )
    if ncm is not None:
        defaults["ncm"] = ncm

    defaults.update(overrides)

    with schema_context(schema_name):
        return Produto(**defaults)


def test_produto_ativo_sem_ncm_dispara_erro(two_tenants_with_admins):
    """
    Cenário:
    - Produto ATIVO, mas sem NCM definido.
    Expectativa:
    - full_clean() deve disparar ValidationError em 'ncm'.
    """
    schema1 = two_tenants_with_admins["schema1"]
    logger.info(
        "Iniciando teste: produto ativo sem NCM deve falhar na validação (schema=%s).",
        schema1,
    )

    ctx = _bootstrap_context(schema1)
    grupo = ctx["grupo"]
    un = ctx["un"]

    produto = _build_produto(schema1, grupo, un, ncm=None)

    with schema_context(schema1):
        with pytest.raises(ValidationError) as exc:
            produto.full_clean()

    assert "ncm" in exc.value.message_dict
    logger.info(
        "Teste concluído: validação de NCM obrigatório para produto ativo funcionando."
    )


@pytest.mark.parametrize(
    "campo",
    ["aliquota_icms", "aliquota_pis", "aliquota_cofins", "aliquota_ipi"],
)
def test_aliquotas_fora_do_intervalo_zero_a_cem_falham(two_tenants_with_admins, campo):
    """
    Cenário:
    - Produto com uma das alíquotas > 100%.
    Expectativa:
    - full_clean() deve falhar indicando o campo específico.
    """
    schema1 = two_tenants_with_admins["schema1"]
    logger.info(
        "Iniciando teste: campo %s com alíquota inválida (>100) deve falhar (schema=%s).",
        campo,
        schema1,
    )

    ctx = _bootstrap_context(schema1)
    grupo = ctx["grupo"]
    un = ctx["un"]
    ncm = ctx["ncm"]

    produto = _build_produto(
        schema1,
        grupo,
        un,
        ncm=ncm,
        **{campo: Decimal("120.00")},
    )

    with schema_context(schema1):
        with pytest.raises(ValidationError) as exc:
            produto.full_clean()

    assert campo in exc.value.message_dict
    logger.info(
        "Teste concluído: validação de faixa de alíquota em %s funcionando.", campo
    )


def test_fator_conversao_tributavel_deve_ser_maior_que_zero(two_tenants_with_admins):
    """
    Cenário:
    - Produto com fator_conversao_tributavel <= 0.
    Expectativa:
    - full_clean() deve falhar.
    """
    schema1 = two_tenants_with_admins["schema1"]
    logger.info(
        "Iniciando teste: fator_conversao_tributavel <= 0 deve falhar (schema=%s).",
        schema1,
    )

    ctx = _bootstrap_context(schema1)
    grupo = ctx["grupo"]
    un = ctx["un"]
    ncm = ctx["ncm"]

    produto = _build_produto(
        schema1,
        grupo,
        un,
        ncm=ncm,
        fator_conversao_tributavel=Decimal("0.000000"),
    )

    with schema_context(schema1):
        with pytest.raises(ValidationError) as exc:
            produto.full_clean()

    # A mensagem vem como erro geral; validamos a presença da string no texto
    assert "fator_conversao_tributavel" in str(exc.value)
    logger.info(
        "Teste concluído: validação de fator_conversao_tributavel funcionando."
    )


def test_get_parametros_fiscais_base_basico(two_tenants_with_admins):
    """
    Cenário:
    - Produto com NCM associado e alíquotas definidas no próprio produto.
    Expectativa:
    - get_parametros_fiscais_base() deve refletir:
        - código do NCM
        - alíquotas do próprio produto
    """
    schema1 = two_tenants_with_admins["schema1"]
    logger.info(
        "Iniciando teste: get_parametros_fiscais_base básico (schema=%s).",
        schema1,
    )

    NCM = apps.get_model("fiscal", "NCM")
    ctx = _bootstrap_context(schema1)
    grupo = ctx["grupo"]
    un = ctx["un"]

    with schema_context(schema1):
        ncm = NCM.objects.create(
            codigo="22030001",
            descricao="NCM para teste de parâmetros fiscais base",
        )

        Produto = apps.get_model("produtos", "Produto")
        produto = Produto.objects.create(
            codigo_interno="PROD_PARAM",
            descricao="Produto com parâmetros fiscais base",
            grupo=grupo,
            unidade_comercial=un,
            unidade_tributavel=un,
            fator_conversao_tributavel=Decimal("1.000000"),
            preco_venda=Decimal("10.000"),
            aliquota_icms=Decimal("18.00"),
            aliquota_pis=Decimal("1.65"),
            aliquota_cofins=Decimal("7.60"),
            aliquota_ipi=Decimal("5.00"),
            aliquota_cbs_especifica=Decimal("3.00"),
            aliquota_ibs_especifica=Decimal("5.00"),
            ativo=True,
            ncm=ncm,
        )

        produto.full_clean()
        params = produto.get_parametros_fiscais_base()

    assert params["ncm_codigo"] == "22030001"
    assert params["aliquota_icms"] == Decimal("18.00")
    assert params["aliquota_pis"] == Decimal("1.65")
    assert params["aliquota_cofins"] == Decimal("7.60")
    assert params["aliquota_ipi"] == Decimal("5.00")
    assert params["aliquota_cbs"] == Decimal("3.00")
    assert params["aliquota_ibs"] == Decimal("5.00")

    logger.info(
        "Teste concluído: get_parametros_fiscais_base retornou parâmetros coerentes com o Produto."
    )


def test_get_cest_principal_retorna_cest_de_menor_codigo(two_tenants_with_admins):
    """
    Cenário:
    - NCM com dois CESTs ativos, de códigos diferentes.
    Expectativa:
    - get_cest_principal() retorna o CEST de menor código (regra atual).
    """
    schema1 = two_tenants_with_admins["schema1"]
    logger.info(
        "Iniciando teste: get_cest_principal com múltiplos CESTs ativos (schema=%s).",
        schema1,
    )

    CEST = apps.get_model("fiscal", "CEST")
    NCM = apps.get_model("fiscal", "NCM")
    ctx = _bootstrap_context(schema1)
    grupo = ctx["grupo"]
    un = ctx["un"]

    with schema_context(schema1):
        ncm = NCM.objects.create(
            codigo="22030002",
            descricao="NCM com múltiplos CEST",
        )
        cest_maior = CEST.objects.create(
            codigo="1234567", descricao="CEST maior", ativo=True
        )
        cest_menor = CEST.objects.create(
            codigo="0123456", descricao="CEST menor", ativo=True
        )
        ncm.cests.add(cest_maior, cest_menor)

        Produto = apps.get_model("produtos", "Produto")
        produto = Produto.objects.create(
            codigo_interno="PROD_CEST",
            descricao="Produto com CEST",
            grupo=grupo,
            unidade_comercial=un,
            unidade_tributavel=un,
            fator_conversao_tributavel=Decimal("1.000000"),
            preco_venda=Decimal("10.000"),
            aliquota_icms=Decimal("0.00"),
            aliquota_pis=Decimal("0.00"),
            aliquota_cofins=Decimal("0.00"),
            ativo=True,
            ncm=ncm,
        )

        produto.full_clean()
        cest_principal = produto.get_cest_principal()

    assert cest_principal is not None
    assert cest_principal.codigo == "0123456"
    logger.info(
        "Teste concluído: get_cest_principal retornou o CEST de menor código conforme esperado."
    )
