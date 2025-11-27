import pytest
from django.db import transaction, models
from django.db.utils import IntegrityError
from django.core.exceptions import ValidationError
from enderecos.models.logradouro_models import Logradouro
from enderecos.models.bairro_models import Bairro
from enderecos.models.municipio_models import Municipio

@pytest.mark.django_db
def test_criar_logradouro_sucesso(bairro_centro):
    """
    Teste Happy Path: Criação de um logradouro e verificação dos campos.
    """
    rua = Logradouro.objects.create(
        tipo=Logradouro.TIPO_RUA,  # "RUA"
        nome="AUGUSTA",
        cep="01304000",
        bairro=bairro_centro
    )

    # 1. Campos simples
    assert rua.nome == "AUGUSTA"
    assert rua.cep == "01304000"
    
    # 2. Teste do get_tipo_display() (Crucial para NFe bonita)
    # O valor no banco é 'RUA', mas o display deve ser 'Rua'
    assert rua.tipo == "RUA"
    assert rua.get_tipo_display() == "Rua"

    # 3. Teste do __str__
    # Formato: "Tipo Nome - Bairro"
    assert str(rua) == f"Rua AUGUSTA - {bairro_centro}"

@pytest.mark.django_db
def test_propriedades_hierarquia(bairro_centro):
    """
    Testa as properties @property que atalham o acesso ao Município e UF.
    Isso garante que a navegação Logradouro -> Bairro -> Municipio -> UF funciona.
    """
    logradouro = Logradouro.objects.create(
        tipo="AV",
        nome="PAULISTA",
        cep="01310100",
        bairro=bairro_centro
    )

    # Verifica se conseguimos chegar no Município através do Logradouro
    assert logradouro.municipio.nome == "SÃO PAULO"
    
    # Verifica se conseguimos chegar na UF através do Logradouro
    assert logradouro.uf.sigla == "SP"

@pytest.mark.django_db
def test_constraint_unicidade_logradouro(bairro_centro):
    """
    Testa a UniqueConstraint:
    Não pode haver (Tipo='RUA', Nome='AUGUSTA', Bairro='CENTRO') duplicado.
    """
    # 1. Cria o original
    Logradouro.objects.create(
        tipo="RUA", nome="AUGUSTA", cep="01304000", bairro=bairro_centro
    )

    # 2. Tenta criar EXATAMENTE o mesmo (deve falhar)
    with transaction.atomic():
        with pytest.raises(IntegrityError):
            Logradouro.objects.create(
                tipo="RUA", nome="AUGUSTA", cep="99999999", bairro=bairro_centro
            )
    
    # 3. Tenta criar com TIPO diferente (deve permitir)
    # Ex: Existe a "Rua Augusta" e hipoteticamente a "Avenida Augusta" no mesmo bairro.
    logradouro_av = Logradouro.objects.create(
        tipo="AV", nome="AUGUSTA", cep="01304000", bairro=bairro_centro
    )
    assert logradouro_av.pk is not None

@pytest.mark.django_db
def test_validacao_cep_tamanho(bairro_centro):
    """
    Testa o validador MinLengthValidator(8) no CEP.
    """
    logradouro = Logradouro(
        tipo="RUA",
        nome="CURTA",
        cep="123",  # Inválido (muito curto)
        bairro=bairro_centro
    )

    with pytest.raises(ValidationError) as excinfo:
        logradouro.full_clean()
    
    assert "cep" in excinfo.value.message_dict

@pytest.mark.django_db
def test_protecao_delecao_bairro(bairro_centro):
    """
    Testa on_delete=models.PROTECT.
    Não deve permitir apagar o Bairro se houver ruas vinculadas a ele.
    """
    Logradouro.objects.create(
        tipo="RUA", nome="TESTE", cep="00000000", bairro=bairro_centro
    )

    # Tentar apagar o bairro deve lançar erro protegido
    with pytest.raises(models.ProtectedError):
        bairro_centro.delete()

@pytest.mark.django_db
def test_ordenacao_logradouros(municipio_sp, municipio_rj):
    """
    Testa a ordenação complexa:
    ordering = ["bairro__municipio__nome", "bairro__nome", "nome"]
    """
    # Cenário: 
    # Rio de Janeiro -> Bairro Cambuí -> Rua Norte Sul
    # São Paulo -> Bairro Centro -> Rua Augusta
    # São Paulo -> Bairro Centro -> Rua Bela Cintra
    
    # Setup Campinas
    bairro_cps = Bairro.objects.create(nome="CAMBUÍ", municipio=municipio_rj)
    rua_cps = Logradouro.objects.create(tipo="AV", nome="NORTE SUL", cep="13000000", bairro=bairro_cps)

    # Setup SP (Já temos bairro_centro fixture, mas precisamos instanciar as ruas)
    # Vamos criar um bairro novo em SP para garantir isolamento se a fixture já tiver dados
    bairro_sp = Bairro.objects.create(nome="CENTRO", municipio=municipio_sp)
    
    rua_sp_b = Logradouro.objects.create(tipo="RUA", nome="BELA CINTRA", cep="01000000", bairro=bairro_sp)
    rua_sp_a = Logradouro.objects.create(tipo="RUA", nome="AUGUSTA", cep="01000000", bairro=bairro_sp)

    # Busca e converte para lista
    lista = list(Logradouro.objects.all())

    # Verificações:
    # 1. Campinas vem antes de São Paulo
    assert lista[0] == rua_cps
    
    # 2. Dentro de SP/Centro, Augusta vem antes de Bela Cintra
    assert lista[1] == rua_sp_a
    assert lista[2] == rua_sp_b