import pytest
from django.db import models
from django.core.exceptions import ValidationError
from enderecos.models.endereco_models import Endereco
from enderecos.models.logradouro_models import Logradouro
from enderecos.models.bairro_models import Bairro
from enderecos.models.municipio_models import Municipio

@pytest.mark.django_db
def test_criar_endereco_sucesso(logradouro_av_paulista):
    """
    Teste Happy Path: Criação básica de um endereço e verificação 
    de campos diretos e formatação (__str__).
    """
    endereco = Endereco.objects.create(
        logradouro=logradouro_av_paulista,
        numero="1578",
        complemento="MASP",
        cep="01310200", 
        referencia="Perto do Trianon"
    )

    # 1. Campos diretos
    assert endereco.numero == "1578"
    assert endereco.complemento == "MASP"
    assert endereco.cep == "01310200"
    assert endereco.referencia == "Perto do Trianon"
    
    # 2. Formatação __str__
    # Esperado: "Avenida PAULISTA - CENTRO , 1578" (Depende do __str__ do Logradouro)
    assert "1578" in str(endereco)
    assert "PAULISTA" in str(endereco)

@pytest.mark.django_db
def test_propriedades_nfe_hierarquia_completa(logradouro_av_paulista):
    """
    TESTE CRÍTICO: Verifica se as properties auxiliares estão 
    buscando os dados corretamente através de todas as tabelas relacionadas.
    Isso garante que a NFe sairá com os dados corretos.
    """
    endereco = Endereco.objects.create(
        logradouro=logradouro_av_paulista,
        numero="1000",
        cep="01310100"
    )

    # 1. Logradouro (xLgr) -> Deve combinar Tipo + Nome
    # O display do tipo "AV" deve ser "Avenida" (conforme choices do Logradouro)
    assert endereco.xLgr == "Avenida PAULISTA"

    # 2. Bairro (xBairro) -> Vem de endereco.logradouro.bairro
    assert endereco.xBairro == "CENTRO"

    # 3. Município (xMun, cMun) -> Vem de ...bairro.municipio
    assert endereco.xMun == "SÃO PAULO"
    assert endereco.cMun == "3550308" # Código IBGE

    # 4. UF (uf) -> Vem de ...municipio.uf
    assert endereco.uf == "SP"

    # 5. País (xPais, cPais) -> Vem de ...uf.pais
    assert endereco.xPais == "BRASIL"
    assert endereco.cPais == "1058" # Código NFe do Brasil

@pytest.mark.django_db
def test_validacao_cep_tamanho(logradouro_av_paulista):
    """
    Testa o MinLengthValidator(8) do campo CEP.
    Lembrando: Validadores só rodam no full_clean(), não no save() direto.
    """
    endereco_invalido = Endereco(
        logradouro=logradouro_av_paulista,
        numero="10",
        cep="12345" # Menor que 8 dígitos
    )

    with pytest.raises(ValidationError) as excinfo:
        endereco_invalido.full_clean()

    assert "cep" in excinfo.value.message_dict

@pytest.mark.django_db
def test_protecao_delecao_logradouro(logradouro_av_paulista):
    """
    Testa a integridade referencial (on_delete=models.PROTECT).
    Não deve ser possível apagar o Logradouro se existir um Endereço vinculado.
    """
    Endereco.objects.create(
        logradouro=logradouro_av_paulista,
        numero="500",
        cep="01310100"
    )

    # Tentar apagar a Rua deve falhar
    with pytest.raises(models.ProtectedError):
        logradouro_av_paulista.delete()

@pytest.mark.django_db
def test_ordenacao_enderecos(municipio_sp, municipio_rj):
    """
    Testa a ordenação complexa definida no Meta:
    ordering = ["logradouro__bairro__municipio__nome", "logradouro__nome", "numero"]
    """
    
    # Criação de estrutura em Campinas (Ordem alfabética C vem antes de S de São Paulo)
    bairro_cps = Bairro.objects.create(nome="CAMBUÍ", municipio=municipio_rj)
    rua_cps = Logradouro.objects.create(nome="NORTE SUL", bairro=bairro_cps, cep="13000000")
    end_campinas = Endereco.objects.create(logradouro=rua_cps, numero="100", cep="13000000")

    # Criação de estrutura em São Paulo (Mesma cidade, ruas diferentes)
    bairro_sp = Bairro.objects.create(nome="JARDINS", municipio=municipio_sp)
    
    # Rua A (Augusta)
    rua_a = Logradouro.objects.create(nome="AUGUSTA", bairro=bairro_sp, cep="01000000")
    end_sp_augusta_10 = Endereco.objects.create(logradouro=rua_a, numero="10", cep="01000000")
    end_sp_augusta_20 = Endereco.objects.create(logradouro=rua_a, numero="20", cep="01000000") # Mesmo nome, numero maior
    
    # Rua B (Paulista)
    rua_b = Logradouro.objects.create(nome="PAULISTA", bairro=bairro_sp, cep="01000000")
    end_sp_paulista = Endereco.objects.create(logradouro=rua_b, numero="100", cep="01000000")

    # Busca todos
    lista = list(Endereco.objects.all())

    # Verificação da Ordem:
    # 1. Campinas (Municipio C) vem antes de São Paulo (Municipio S)
    assert lista[0] == end_campinas
    
    # 2. Dentro de SP, Augusta (Rua A) vem antes de Paulista (Rua P)
    assert lista[1] == end_sp_augusta_10
    
    # 3. Dentro de Augusta, Número 10 vem antes de Número 20 (String comparison "10" < "20")
    # Nota: Como 'numero' é CharField, a ordenação é alfanumérica ("10" vem antes de "2"), cuidado com isso.
    assert lista[2] == end_sp_augusta_20
    assert lista[3] == end_sp_paulista