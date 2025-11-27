# filial/tests/nfce/test_nfce_config_cascade_delete.py

import logging

import pytest
from django.apps import apps
from django_tenants.utils import schema_context

logger = logging.getLogger(__name__)


@pytest.mark.django_db(transaction=True)
def test_nfce_config_excluida_ao_deletar_filial(two_tenants_with_admins):
    """
    Garante que ao excluir a Filial, sua FilialNFCeConfig é excluída junto (CASCADE).

    Cenário:
    - No tenant1, criamos FilialNFCeConfig para a filial inicial.
    - Deletamos a filial.
    - Validamos que a config também foi removida.
    """
    schema1 = two_tenants_with_admins["schema1"]

    FilialModel = apps.get_model("filial", "Filial")
    FilialNFCeConfig = apps.get_model("filial", "FilialNFCeConfig")

    with schema_context(schema1):
        filial = FilialModel.objects.first()
        assert filial is not None, "Deve existir uma filial inicial."

        config = FilialNFCeConfig.objects.create(
            filial=filial,
            ambiente=FilialNFCeConfig.AMBIENTE_HOMOLOGACAO,
            csc_id="CSC_DEL",
            csc_token="TOKEN_DEL",
        )
        assert FilialNFCeConfig.objects.filter(pk=config.pk).exists()

        logger.info(
            "Deletando filial_id=%s e verificando remoção da FilialNFCeConfig.",
            filial.id,
        )
        filial.delete()

        assert not FilialNFCeConfig.objects.filter(pk=config.pk).exists(), (
            "Config NFC-e não deve existir após exclusão da filial."
        )
        logger.info("Confirmação: FilialNFCeConfig removida via CASCADE.")
