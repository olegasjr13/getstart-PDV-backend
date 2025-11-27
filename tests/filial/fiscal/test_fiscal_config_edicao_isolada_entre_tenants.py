# filial/tests/fiscal/test_fiscal_config_edicao_isolada_entre_tenants.py

import logging

import pytest
from django.apps import apps
from django_tenants.utils import schema_context

logger = logging.getLogger(__name__)


@pytest.mark.django_db(transaction=True)
def test_edicao_config_fiscal_no_tenant1_nao_afeta_tenant2(two_tenants_with_admins):
    """
    Cenário:
    - Criamos config fiscal para a filial inicial de AMBOS os tenants.
    - Alteramos cnae_principal e tipo_contrib_icms do tenant1.

    Valida:
    - Config fiscal do tenant1 é atualizada.
    - Config fiscal do tenant2 permanece com valores originais.
    """
    schema1 = two_tenants_with_admins["schema1"]
    schema2 = two_tenants_with_admins["schema2"]

    FilialModel = apps.get_model("filial", "Filial")
    FilialFiscalConfig = apps.get_model("filial", "FilialFiscalConfig")

    # Criar configs iniciais
    with schema_context(schema1):
        filial1 = FilialModel.objects.first()
        cfg1 = FilialFiscalConfig.objects.create(
            filial=filial1,
            inscricao_estadual="IE_T1",
            inscricao_municipal="IM_T1",
            cnae_principal="4711301",
            regime_tributario="1",
            tipo_contrib_icms="1",
        )

    with schema_context(schema2):
        filial2 = FilialModel.objects.first()
        cfg2 = FilialFiscalConfig.objects.create(
            filial=filial2,
            inscricao_estadual="IE_T2",
            inscricao_municipal="IM_T2",
            cnae_principal="5611203",
            regime_tributario="3",
            tipo_contrib_icms="9",
        )

    # Editar config do tenant1
    with schema_context(schema1):
        cfg1 = FilialFiscalConfig.objects.get(pk=cfg1.pk)
        cfg1.cnae_principal = "6201501"
        cfg1.tipo_contrib_icms = "2"
        cfg1.save(update_fields=["cnae_principal", "tipo_contrib_icms"])

    # Validar que tenant2 continua intacto
    with schema_context(schema2):
        cfg2_r = FilialFiscalConfig.objects.get(pk=cfg2.pk)
        assert cfg2_r.cnae_principal == "5611203"
        assert cfg2_r.tipo_contrib_icms == "9", (
            "Alterar config fiscal no tenant1 não pode mexer nos dados fiscais do tenant2."
        )
