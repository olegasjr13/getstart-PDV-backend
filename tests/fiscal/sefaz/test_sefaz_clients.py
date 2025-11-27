import uuid

from fiscal.sefaz_clients import MockSefazClient


def test_mock_sefaz_client_autorizar_nfce_retorna_chave_e_protocolo():
    client = MockSefazClient(ambiente="homolog", uf="SP")

    class _Filial:
        uf = "SP"
        ambiente = "homolog"

    class _Pre:
        request_id = uuid.uuid4()

    resp = client.autorizar_nfce(
        filial=_Filial(),
        pre_emissao=_Pre(),
        numero=1,
        serie=1,
    )

    assert resp.codigo == 100
    assert resp.chave_acesso.startswith("NFe")
    assert len(resp.chave_acesso) <= 44
    assert resp.protocolo
    assert resp.raw["ambiente"] == "homolog"
    assert resp.raw["uf"] == "SP"
