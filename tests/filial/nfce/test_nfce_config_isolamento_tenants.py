# filial/tests/nfce/test_nfce_config_isolamento_tenants.py

import logging

import pytest
from django.apps import apps
from django_tenants.utils import schema_context

logger = logging.getLogger(__name__)


@pytest.mark.django_db(transaction=True)
def test_nfce_config_criada_no_tenant1_nao_existe_no_tenant2(two_tenants_with_admins):
    """
    Cenário:
    - Tenant1 e Tenant2 provisionados.
    - No tenant1, criamos uma FilialNFCeConfig para a filial inicial.
    - No tenant2, não criamos nenhuma NFCeConfig.

    Valida:
    - Config NFC-e existe apenas no tenant1.
    - No tenant2 NÃO há config NFC-e para nenhuma filial.
    """
    schema1 = two_tenants_with_admins["schema1"]
    schema2 = two_tenants_with_admins["schema2"]

    FilialModel = apps.get_model("filial", "Filial")
    FilialNFCeConfig = apps.get_model("filial", "FilialNFCeConfig")

    # Tenant1: cria config NFC-e
    with schema_context(schema1):
        logger.info("Criando FilialNFCeConfig no tenant1 (schema=%s).", schema1)

        filial = FilialModel.objects.first()
        assert filial is not None, "Deve existir uma filial inicial no tenant1."

        config = FilialNFCeConfig.objects.create(
            filial=filial,
            ambiente=FilialNFCeConfig.AMBIENTE_HOMOLOGACAO,
            csc_id="CSC_T1",
            csc_token="TOKEN_T1",
            modelo_impressao="TERMICA80",
        )

        assert FilialNFCeConfig.objects.filter(pk=config.pk).exists()
        logger.info(
            "FilialNFCeConfig criada no tenant1 para filial_id=%s.", filial.id
        )

    # Tenant2: não deve ter nenhuma NFCeConfig
    with schema_context(schema2):
        logger.info("Verificando ausência de FilialNFCeConfig no tenant2 (schema=%s).", schema2)
        assert FilialNFCeConfig.objects.count() == 0, (
            "Tenant2 não deve possuir nenhuma configuração NFC-e "
            "quando criada apenas no tenant1."
        )
        logger.info("Confirmação: nenhum registro de FilialNFCeConfig no tenant2.")
