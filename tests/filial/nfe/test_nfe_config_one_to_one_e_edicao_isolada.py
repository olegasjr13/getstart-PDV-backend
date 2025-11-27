# filial/tests/nfe/test_nfe_config_one_to_one_e_edicao_isolada.py

import logging

import pytest
from django.apps import apps
from django.db import IntegrityError
from django_tenants.utils import schema_context

logger = logging.getLogger(__name__)


@pytest.mark.django_db(transaction=True)
def test_nfe_config_one_to_one_e_edicao_nao_afeta_outros(two_tenants_with_admins):
    """
    Cenário:
    - No tenant1:
        * Criamos 2 filiais (inicial + extra).
        * Criamos uma FilialNFeConfig para cada.
        * Alteramos a natureza_operacao_padrao da filial1.

    Valida:
    - OneToOne impede 2 configs para a MESMA filial.
    - Alterar config da filial1 NÃO altera a config da filial2.
    """
    schema1 = two_tenants_with_admins["schema1"]

    FilialModel = apps.get_model("filial", "Filial")
    FilialNFeConfig = apps.get_model("filial", "FilialNFeConfig")

    with schema_context(schema1):
        filial1 = FilialModel.objects.first()
        assert filial1 is not None
        endereco = filial1.endereco

        filial2 = FilialModel.objects.create(
            razao_social="Filial 2 NF-e",
            nome_fantasia="Loja 2 NF-e",
            cnpj="66666666000100",
            endereco=endereco,
            ativo=True,
        )

        cfg1 = FilialNFeConfig.objects.create(
            filial=filial1,
            ambiente=FilialNFeConfig.AMBIENTE_HOMOLOGACAO,
            natureza_operacao_padrao="VENDA PADRAO 1",
            versao_layout="4.00",
        )
        cfg2 = FilialNFeConfig.objects.create(
            filial=filial2,
            ambiente=FilialNFeConfig.AMBIENTE_HOMOLOGACAO,
            natureza_operacao_padrao="VENDA PADRAO 2",
            versao_layout="4.00",
        )

        # Teste OneToOne
        with pytest.raises(IntegrityError):
            FilialNFeConfig.objects.create(
                filial=filial1,
                ambiente=FilialNFeConfig.AMBIENTE_PRODUCAO,
                natureza_operacao_padrao="DUPLICADO",
                versao_layout="4.00",
            )

        # Editar cfg1 não pode mexer em cfg2
        cfg1.natureza_operacao_padrao = "VENDA ALTERADA 1"
        cfg1.save(update_fields=["natureza_operacao_padrao"])

        cfg1_refresh = FilialNFeConfig.objects.get(pk=cfg1.pk)
        cfg2_refresh = FilialNFeConfig.objects.get(pk=cfg2.pk)

        assert cfg1_refresh.natureza_operacao_padrao == "VENDA ALTERADA 1"
        assert cfg2_refresh.natureza_operacao_padrao == "VENDA PADRAO 2", (
            "Alterar config NF-e da filial1 NÃO pode afetar a config da filial2."
        )
