import pytest
from django.db import transaction
from django.db.utils import IntegrityError
from django.core.exceptions import ValidationError
from enderecos.models.municipio_models import Municipio

@pytest.mark.django_db
def test_criar_municipio_sucesso(uf_sp):
    """
    Testa o caminho feliz: criar um Município vinculado a uma UF.
    """
    municipio = Municipio.objects.create(
        nome="SÃO PAULO",
        codigo_ibge="3550308",
        uf=uf_sp
    )

    # 1. Verificações de campos
    assert municipio.nome == "SÃO PAULO"
    assert municipio.codigo_ibge == "3550308"
    
    # 2. Teste da Property auxiliar para NFe
    assert municipio.codigo_nfe == "3550308"

    # 3. Verificação de Relacionamento
    assert municipio.uf == uf_sp
    assert municipio.uf.sigla == "SP"

    # 4. Verificação do __str__ (Formato: "Nome / SiglaUF")
    assert str(municipio) == "SÃO PAULO / SP"

@pytest.mark.django_db
def test_municipio_relacionamento_reverso(uf_sp):
    """
    Testa se conseguimos acessar os municípios a partir da UF.
    """
    Municipio.objects.create(nome="SANTOS", codigo_ibge="3548500", uf=uf_sp)
    Municipio.objects.create(nome="CAMPINAS", codigo_ibge="3509502", uf=uf_sp)

    # uf_sp.municipios deve conter 2 registros
    assert uf_sp.municipios.count() == 2
    assert uf_sp.municipios.filter(nome="SANTOS").exists()

@pytest.mark.django_db
def test_unicidade_municipio(uf_sp, uf_rj):
    """
    Testa as constraints:
    1. codigo_ibge deve ser único globalmente.
    2. Combinação (nome, uf) deve ser única.
    """
    # Cria registro base
    Municipio.objects.create(nome="TESTE", codigo_ibge="1111111", uf=uf_sp)

    # Cenário A: Duplicidade de IBGE (Não pode repetir o código mesmo em outra UF)
    with transaction.atomic():
        with pytest.raises(IntegrityError):
            Municipio.objects.create(nome="OUTRO", codigo_ibge="1111111", uf=uf_rj)

    # Cenário B: Duplicidade de Nome na MESMA UF (Constraint uniq_municipio_nome_uf)
    with transaction.atomic():
        with pytest.raises(IntegrityError):
            Municipio.objects.create(nome="TESTE", codigo_ibge="2222222", uf=uf_sp)

    # Cenário C: Mesmo nome em UF DIFERENTE (Deve permitir)
    # Ex: Existe "Bom Jesus" em vários estados.
    municipio_rj = Municipio.objects.create(nome="TESTE", codigo_ibge="3333333", uf=uf_rj)
    assert municipio_rj.pk is not None  # Sucesso

@pytest.mark.django_db
def test_validacao_tamanho_ibge(uf_sp):
    """
    Testa o validador MinLengthValidator(7).
    Nota: Validators do Django não rodam automaticamente no .save(), 
    é preciso chamar .full_clean().
    """
    municipio = Municipio(
        nome="CURTO",
        codigo_ibge="123",  # Menor que 7 dígitos
        uf=uf_sp
    )

    # O save() passaria direto se não validarmos antes ou se o banco não tiver constraint de tamanho
    # Por isso testamos o full_clean() que é o que o Django Admin/Forms usam.
    with pytest.raises(ValidationError) as excinfo:
        municipio.full_clean()
    
    # Verifica se o erro está no campo codigo_ibge
    assert "codigo_ibge" in excinfo.value.message_dict