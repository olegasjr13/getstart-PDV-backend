# filial/tests/nfe/test_nfe_config_isolamento_tenants.py

import logging

import pytest
from django.apps import apps
from django_tenants.utils import schema_context

logger = logging.getLogger(__name__)


@pytest.mark.django_db(transaction=True)
def test_nfe_config_criada_no_tenant1_nao_existe_no_tenant2(two_tenants_with_admins):
    """
    Cenário:
    - No tenant1 criamos FilialNFeConfig para a filial inicial.
    - Tenant2 não recebe nenhuma config NF-e.

    Valida:
    - Config NF-e existe apenas no tenant1.
    - Tenant2 permanece sem registros NF-e.
    """
    schema1 = two_tenants_with_admins["schema1"]
    schema2 = two_tenants_with_admins["schema2"]

    FilialModel = apps.get_model("filial", "Filial")
    FilialNFeConfig = apps.get_model("filial", "FilialNFeConfig")

    # Tenant1
    with schema_context(schema1):
        filial = FilialModel.objects.first()
        assert filial is not None

        FilialNFeConfig.objects.create(
            filial=filial,
            ambiente=FilialNFeConfig.AMBIENTE_HOMOLOGACAO,
            natureza_operacao_padrao="VENDA DE MERCADORIA",
            versao_layout="4.00",
        )

        assert FilialNFeConfig.objects.count() == 1

    # Tenant2
    with schema_context(schema2):
        assert FilialNFeConfig.objects.count() == 0, (
            "Tenant2 não deve possuir configurações NF-e criadas em tenant1."
        )
