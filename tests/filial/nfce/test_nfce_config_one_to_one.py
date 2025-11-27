# filial/tests/nfce/test_nfce_config_one_to_one.py

import logging

import pytest
from django.apps import apps
from django.db import IntegrityError
from django_tenants.utils import schema_context

logger = logging.getLogger(__name__)


@pytest.mark.django_db(transaction=True)
def test_nfce_config_one_to_one_por_filial(two_tenants_with_admins):
    """
    Garante que cada Filial só pode ter UMA FilialNFCeConfig (OneToOneField).

    Cenário:
    - No tenant1, criamos uma config NFC-e para a filial inicial.
    - Tentamos criar UMA SEGUNDA config para a mesma filial.

    Esperado:
    - IntegrityError ao tentar inserir a segunda config.
    """
    schema1 = two_tenants_with_admins["schema1"]

    FilialModel = apps.get_model("filial", "Filial")
    FilialNFCeConfig = apps.get_model("filial", "FilialNFCeConfig")

    with schema_context(schema1):
        filial = FilialModel.objects.first()
        assert filial is not None, "Deve existir uma filial inicial no tenant1."

        logger.info(
            "Criando primeira FilialNFCeConfig para filial_id=%s no tenant1.", filial.id
        )
        FilialNFCeConfig.objects.create(
            filial=filial,
            ambiente=FilialNFCeConfig.AMBIENTE_HOMOLOGACAO,
            csc_id="CSC_UNICO",
            csc_token="TOKEN_UNICO",
        )

        logger.info(
            "Tentando criar segunda FilialNFCeConfig para a MESMA filial (deve falhar)."
        )
        with pytest.raises(IntegrityError):
            FilialNFCeConfig.objects.create(
                filial=filial,
                ambiente=FilialNFCeConfig.AMBIENTE_PRODUCAO,
                csc_id="CSC_DUP",
                csc_token="TOKEN_DUP",
            )

        logger.info(
            "Fim: constraint OneToOne de FilialNFCeConfig respeitada (duplicidade bloqueada)."
        )
