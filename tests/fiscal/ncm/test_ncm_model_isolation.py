# fiscal/tests/ncm/test_ncm_model_isolation.py

import logging
from datetime import date

import pytest
from django.apps import apps
from django_tenants.utils import get_tenant_model, schema_context

logger = logging.getLogger(__name__)

# Precisamos de transação por causa de django-tenants + schema_context
pytestmark = pytest.mark.django_db(transaction=True)


def _get_tenants():
    Tenant = get_tenant_model()
    t1 = Tenant.objects.get(schema_name="99666666000191")
    t2 = Tenant.objects.get(schema_name="99777777000191")
    return t1, t2


@pytest.mark.usefixtures("two_tenants_with_admins")
def test_ncm_criacao_isolada_por_tenant():
    """
    Criação de NCM em tenant1 NÃO deve aparecer no tenant2.
    """
    NCM = apps.get_model("fiscal", "NCM")
    tenant1, tenant2 = _get_tenants()

    logger.info(
        "Iniciando teste: criação de NCM no tenant1 não deve aparecer no tenant2."
    )

    # Cria 2 NCMs no tenant1
    with schema_context(tenant1.schema_name):
        NCM.objects.create(
            codigo="01012100",
            descricao="Cavalos reprodutores de raça pura",
            vigencia_inicio=date(2017, 1, 1),
            ativo=True,
        )
        NCM.objects.create(
            codigo="01012900",
            descricao="Outros cavalos",
            vigencia_inicio=date(2017, 1, 1),
            ativo=True,
        )
        assert NCM.objects.count() == 2

    # No tenant2, nada disso deve existir
    with schema_context(tenant2.schema_name):
        assert NCM.objects.count() == 0
        assert not NCM.objects.filter(codigo="01012100").exists()
        assert not NCM.objects.filter(codigo="01012900").exists()

    logger.info(
        "Fim teste: criação de NCM no tenant1 confirmada como isolada do tenant2."
    )


@pytest.mark.usefixtures("two_tenants_with_admins")
def test_ncm_atualizacao_nao_afeta_outro_tenant():
    """
    Atualizar um NCM em tenant1 NÃO deve alterar o NCM de mesmo código em tenant2.
    """
    NCM = apps.get_model("fiscal", "NCM")
    tenant1, tenant2 = _get_tenants()

    logger.info(
        "Iniciando teste: atualização de NCM no tenant1 não deve afetar tenant2."
    )

    # Cria NCM igual (mesmo código) nos dois tenants, com descrições diferentes
    with schema_context(tenant1.schema_name):
        ncm_t1 = NCM.objects.create(
            codigo="22030000",
            descricao="Cervejas de malte - tenant1",
            vigencia_inicio=date(2025, 1, 1),
            ativo=True,
        )

    with schema_context(tenant2.schema_name):
        ncm_t2 = NCM.objects.create(
            codigo="22030000",
            descricao="Cervejas de malte - tenant2",
            vigencia_inicio=date(2025, 1, 1),
            ativo=True,
        )

    # Atualiza apenas no tenant1
    with schema_context(tenant1.schema_name):
        ncm_t1.descricao = "Cervejas de malte - ATUALIZADO tenant1"
        ncm_t1.save(update_fields=["descricao"])

        ncm_t1_db = NCM.objects.get(pk=ncm_t1.pk)
        assert ncm_t1_db.descricao == "Cervejas de malte - ATUALIZADO tenant1"

    # Confirma que tenant2 continua intacto
    with schema_context(tenant2.schema_name):
        ncm_t2_db = NCM.objects.get(pk=ncm_t2.pk)
        assert ncm_t2_db.descricao == "Cervejas de malte - tenant2"

    logger.info(
        "Fim teste: atualização em tenant1 não afetou o registro correspondente em tenant2."
    )


@pytest.mark.usefixtures("two_tenants_with_admins")
def test_ncm_exclusao_nao_afeta_outro_tenant():
    """
    Excluir um NCM em tenant1 NÃO deve excluir o NCM de mesmo código em tenant2.
    """
    NCM = apps.get_model("fiscal", "NCM")
    tenant1, tenant2 = _get_tenants()

    logger.info(
        "Iniciando teste: exclusão de NCM no tenant1 não deve afetar tenant2."
    )

    with schema_context(tenant1.schema_name):
        ncm_t1 = NCM.objects.create(
            codigo="30049099",
            descricao="Medicamentos diversos - tenant1",
            vigencia_inicio=date(2024, 1, 1),
            ativo=True,
        )

    with schema_context(tenant2.schema_name):
        ncm_t2 = NCM.objects.create(
            codigo="30049099",
            descricao="Medicamentos diversos - tenant2",
            vigencia_inicio=date(2024, 1, 1),
            ativo=True,
        )

    # Exclui no tenant1
    with schema_context(tenant1.schema_name):
        NCM.objects.filter(pk=ncm_t1.pk).delete()
        assert not NCM.objects.filter(pk=ncm_t1.pk).exists()

    # Confirma que no tenant2 continua existindo
    with schema_context(tenant2.schema_name):
        assert NCM.objects.filter(pk=ncm_t2.pk).exists()
        ncm_t2_db = NCM.objects.get(pk=ncm_t2.pk)
        assert ncm_t2_db.codigo == "30049099"
        assert ncm_t2_db.descricao == "Medicamentos diversos - tenant2"

    logger.info(
        "Fim teste: exclusão de NCM no tenant1 não removeu o registro correspondente em tenant2."
    )


@pytest.mark.usefixtures("two_tenants_with_admins")
def test_ncm_inativacao_nao_afeta_outro_tenant():
    """
    Inativar um NCM (ativo=False) em tenant1 NÃO deve inativar o NCM de mesmo código em tenant2.
    """
    NCM = apps.get_model("fiscal", "NCM")
    tenant1, tenant2 = _get_tenants()

    logger.info(
        "Iniciando teste: inativação de NCM no tenant1 não deve afetar tenant2."
    )

    with schema_context(tenant1.schema_name):
        ncm_t1 = NCM.objects.create(
            codigo="19053100",
            descricao="Biscoitos e bolachas doces - tenant1",
            vigencia_inicio=date(2024, 1, 1),
            ativo=True,
        )

    with schema_context(tenant2.schema_name):
        ncm_t2 = NCM.objects.create(
            codigo="19053100",
            descricao="Biscoitos e bolachas doces - tenant2",
            vigencia_inicio=date(2024, 1, 1),
            ativo=True,
        )

    # Inativa no tenant1
    with schema_context(tenant1.schema_name):
        ncm_t1.ativo = False
        ncm_t1.save(update_fields=["ativo"])
        ncm_t1_db = NCM.objects.get(pk=ncm_t1.pk)
        assert ncm_t1_db.ativo is False

    # Confirma que tenant2 continua ativo
    with schema_context(tenant2.schema_name):
        ncm_t2_db = NCM.objects.get(pk=ncm_t2.pk)
        assert ncm_t2_db.ativo is True

    logger.info(
        "Fim teste: inativação em tenant1 não afetou o registro correspondente em tenant2."
    )
