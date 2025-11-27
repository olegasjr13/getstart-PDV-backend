# fiscal/tests/sefaz/test_sefaz_factory_multi_uf.py
import pytest
from django.test import override_settings

from django_tenants.utils import schema_context

from filial.models import Filial
from fiscal.sefaz_factory import get_sefaz_client_for_filial
from fiscal.sefaz_clients import MockSefazClient, MockSefazClientAlwaysFail
from fiscal.tests.test_nfce_atomicidade_rollback import TENANT_SCHEMA
from fiscal.tests.test_nfce_auditoria_logs import _bootstrap_public_tenant_and_domain


@pytest.mark.django_db(transaction=True)
@override_settings(
    ROOT_URLCONF="config.urls",
)
def test_get_sefaz_client_for_filial_multi_uf_homolog():
    """
    Garante que, para SP/MG/RJ/ES em homologação, o factory retorna
    instâncias de MockSefazClient com UF e ambiente coerentes.
    """
    _bootstrap_public_tenant_and_domain()

    ufs = ["SP", "MG", "RJ", "ES"]

    with schema_context(TENANT_SCHEMA):
        for uf in ufs:
            filial = Filial.objects.create(
                cnpj=f"99{ufs.index(uf)+1:02d}{ufs.index(uf)+1:02d}0001{ufs.index(uf)+1:02d}",
                nome_fantasia=f"Filial {uf} Homolog",
                uf=uf,
                csc_id="ID",
                csc_token="TK",
                ambiente="homolog",
            )

            client = get_sefaz_client_for_filial(filial)

            assert isinstance(client, MockSefazClient)
            assert client.uf == uf
            assert client.ambiente == "homolog"


@pytest.mark.django_db(transaction=True)
@override_settings(
    ROOT_URLCONF="config.urls",
)
def test_get_sefaz_client_for_filial_multi_uf_producao():
    """
    Garante que, para SP/MG/RJ/ES em produção, o factory retorna
    instâncias de MockSefazClient com ambiente 'producao'.
    """
    _bootstrap_public_tenant_and_domain()

    ufs = ["SP", "MG", "RJ", "ES"]

    with schema_context(TENANT_SCHEMA):
        for uf in ufs:
            filial = Filial.objects.create(
                cnpj=f"88{ufs.index(uf)+1:02d}{ufs.index(uf)+1:02d}0001{ufs.index(uf)+1:02d}",
                nome_fantasia=f"Filial {uf} Prod",
                uf=uf,
                csc_id="ID",
                csc_token="TK",
                ambiente="producao",
            )

            client = get_sefaz_client_for_filial(filial)

            assert isinstance(client, MockSefazClient)
            assert client.uf == uf
            assert client.ambiente == "producao"


@pytest.mark.django_db(transaction=True)
@override_settings(
    ROOT_URLCONF="config.urls",
)
def test_get_sefaz_client_for_filial_force_technical_fail():
    """
    Garante que force_technical_fail=True devolve MockSefazClientAlwaysFail,
    preservando UF/ambiente.
    """
    _bootstrap_public_tenant_and_domain()

    with schema_context(TENANT_SCHEMA):
        filial = Filial.objects.create(
            cnpj="77112233000199",
            nome_fantasia="Filial SP Falha Técnica",
            uf="SP",
            csc_id="ID",
            csc_token="TK",
            ambiente="homolog",
        )

        client = get_sefaz_client_for_filial(filial, force_technical_fail=True)

        assert isinstance(client, MockSefazClientAlwaysFail)
        assert client.uf == "SP"
        assert client.ambiente == "homolog"
