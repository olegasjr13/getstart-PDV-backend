# filial/tests/fiscal/test_fiscal_config_edicao_isolada_mesmo_tenant.py

import logging

import pytest
from django.apps import apps
from django_tenants.utils import schema_context

logger = logging.getLogger(__name__)


@pytest.mark.django_db(transaction=True)
def test_edicao_config_fiscal_de_uma_filial_nao_afeta_outra_no_mesmo_tenant(two_tenants_with_admins):
    """
    Cenário:
    - No tenant1:
        * Temos filial1 inicial.
        * Criamos filial2.
        * Criamos FilialFiscalConfig para ambas.
        * Alteramos IE e regime_tributario da filial1.

    Valida:
    - Alterações da config fiscal da filial1 NÃO afetam a config da filial2.
    """
    schema1 = two_tenants_with_admins["schema1"]

    FilialModel = apps.get_model("filial", "Filial")
    FilialFiscalConfig = apps.get_model("filial", "FilialFiscalConfig")

    with schema_context(schema1):
        filial1 = FilialModel.objects.first()
        endereco = filial1.endereco

        filial2 = FilialModel.objects.create(
            razao_social="Filial Fiscal 2",
            nome_fantasia="Loja Fiscal 2",
            cnpj="77777777000100",
            endereco=endereco,
            ativo=True,
        )

        cfg1 = FilialFiscalConfig.objects.create(
            filial=filial1,
            inscricao_estadual="IE1",
            inscricao_municipal="IM1",
            cnae_principal="4711301",
            regime_tributario="1",
        )
        cfg2 = FilialFiscalConfig.objects.create(
            filial=filial2,
            inscricao_estadual="IE2",
            inscricao_municipal="IM2",
            cnae_principal="5611203",
            regime_tributario="3",
        )

        # Edita cfg1
        cfg1.inscricao_estadual = "IE1_EDITADA"
        cfg1.regime_tributario = "2"
        cfg1.save(update_fields=["inscricao_estadual", "regime_tributario"])

        cfg1_r = FilialFiscalConfig.objects.get(pk=cfg1.pk)
        cfg2_r = FilialFiscalConfig.objects.get(pk=cfg2.pk)

        assert cfg1_r.inscricao_estadual == "IE1_EDITADA"
        assert cfg1_r.regime_tributario == "2"

        # cfg2 deve permanecer intacta
        assert cfg2_r.inscricao_estadual == "IE2"
        assert cfg2_r.regime_tributario == "3", (
            "Editar config fiscal da filial1 não pode alterar a config da filial2."
        )
