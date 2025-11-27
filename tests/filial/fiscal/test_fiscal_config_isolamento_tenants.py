# filial/tests/fiscal/test_fiscal_config_isolamento_tenants.py

import logging

import pytest
from django.apps import apps
from django_tenants.utils import schema_context

logger = logging.getLogger(__name__)


@pytest.mark.django_db(transaction=True)
def test_fiscal_config_criada_no_tenant1_nao_existe_no_tenant2(two_tenants_with_admins):
    """
    Cenário:
    - Criamos FilialFiscalConfig para a filial inicial do tenant1.
    - Tenant2 não recebe nenhuma config fiscal.

    Valida:
    - Tenant1 possui 1 config fiscal.
    - Tenant2 não possui nenhuma.
    """
    schema1 = two_tenants_with_admins["schema1"]
    schema2 = two_tenants_with_admins["schema2"]

    FilialModel = apps.get_model("filial", "Filial")
    FilialFiscalConfig = apps.get_model("filial", "FilialFiscalConfig")

    with schema_context(schema1):
        filial = FilialModel.objects.first()
        FilialFiscalConfig.objects.create(
            filial=filial,
            inscricao_estadual="ISENTO",
            inscricao_municipal="",
            cnae_principal="4711301",
            regime_tributario="1",
        )
        assert FilialFiscalConfig.objects.count() == 1

    with schema_context(schema2):
        assert FilialFiscalConfig.objects.count() == 0, (
            "Config fiscal criada no tenant1 não pode aparecer no tenant2."
        )
