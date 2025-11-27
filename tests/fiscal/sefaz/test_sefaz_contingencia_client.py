import pytest

from fiscal.sefaz_clients import (
    MockSefazClientAlwaysFail,
    SefazTechnicalError,
)


class _FilialStub:
    """
    Stub mínimo de Filial para uso nos testes do client de contingência.
    Não depende da model real, só fornece os atributos acessados.
    """

    def __init__(self, uf="SP", ambiente="homolog"):
        self.uf = uf
        self.ambiente = ambiente


class _PreEmissaoStub:
    """
    Stub mínimo de pré-emissão. O client MockSefazClientAlwaysFail
    não usa esses dados, mas mantemos a assinatura compatível.
    """

    def __init__(self):
        self.numero = 1
        self.serie = 1


@pytest.mark.django_db
def test_mock_sefaz_client_always_fail_autorizar_nfce_raises_sefaz_technical_error():
    """
    Garante que o MockSefazClientAlwaysFail SEMPRE lança SefazTechnicalError
    ao tentar autorizar uma NFC-e (via autorizar_nfce), simulando
    indisponibilidade técnica da SEFAZ.
    """

    client = MockSefazClientAlwaysFail(ambiente="homolog", uf="SP")

    filial = _FilialStub(uf="SP", ambiente="homolog")
    pre = _PreEmissaoStub()

    with pytest.raises(SefazTechnicalError) as excinfo:
        client.autorizar_nfce(
            filial=filial,
            pre_emissao=pre,
            numero=pre.numero,
            serie=pre.serie,
        )

    err = excinfo.value
    assert "Falha técnica simulada" in str(err)
    assert err.codigo == "TECH_FAIL"
    assert isinstance(err.raw, dict)
    assert err.raw.get("uf") == "SP"
    assert err.raw.get("ambiente") == "homolog"


@pytest.mark.django_db
def test_mock_sefaz_client_always_fail_emitir_nfce_raises_sefaz_technical_error():
    """
    Garante que o MockSefazClientAlwaysFail também lança SefazTechnicalError
    ao chamar emitir_nfce(pre_emissao=...), que é o método usado diretamente
    pela service de emissão em testes de contingência.
    """

    client = MockSefazClientAlwaysFail(ambiente="homolog", uf="SP")
    pre = _PreEmissaoStub()

    with pytest.raises(SefazTechnicalError) as excinfo:
        client.emitir_nfce(pre_emissao=pre)

    err = excinfo.value
    assert "Falha técnica simulada" in str(err)
    assert err.codigo == "TECH_FAIL"
    assert isinstance(err.raw, dict)
    # Aqui o raw vem da própria instância (self), não de uma filial.
    assert err.raw.get("uf") == "SP"
    assert err.raw.get("ambiente") == "homolog"
