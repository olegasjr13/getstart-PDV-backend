from filial.models.filial_models import Filial
from fiscal.sefaz_factory import get_sefaz_client_for_filial
from fiscal.sefaz_clients import MockSefazClient


def test_get_sefaz_client_for_filial_retorna_mock_para_sp_homolog(db):
    filial = Filial(
        cnpj="99999999000199",
        nome_fantasia="Filial Factory",
        uf="SP",
        csc_id="ID",
        csc_token="TK",
        ambiente="homolog",
    )

    client = get_sefaz_client_for_filial(filial)

    assert isinstance(client, MockSefazClient)
    assert client.ambiente == "homolog"
    assert client.uf == "SP"
