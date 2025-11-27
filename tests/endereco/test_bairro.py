import pytest
from django.db import transaction, models
from django.db.utils import IntegrityError
from django.core.exceptions import ValidationError
from enderecos.models.bairro_models import Bairro
from enderecos.models.municipio_models import Municipio

@pytest.mark.django_db
def test_criar_bairro_sucesso(municipio_sp):
    """
    Teste básico (Happy Path): Criação de um bairro válido.
    """
    bairro = Bairro.objects.create(
        nome="VILA MADALENA",
        municipio=municipio_sp
    )

    assert bairro.nome == "VILA MADALENA"
    assert bairro.municipio == municipio_sp
    # Teste do __str__
    assert str(bairro) == f"VILA MADALENA - {municipio_sp}"

@pytest.mark.django_db
def test_bairro_constraint_unicidade(municipio_sp):
    """
    Testa a UniqueConstraint: Não pode haver dois bairros com o mesmo NOME
    dentro do MESMO município.
    """
    # 1. Cria o original
    Bairro.objects.create(nome="CENTRO", municipio=municipio_sp)

    # 2. Tenta criar duplicado no MESMO município
    with transaction.atomic():
        with pytest.raises(IntegrityError) as excinfo:
            Bairro.objects.create(nome="CENTRO", municipio=municipio_sp)
    
    # Verifica se o erro menciona a constraint correta (opcional, mas robusto)
    assert "uniq_bairro_nome_municipio" in str(excinfo.value)

@pytest.mark.django_db
def test_bairros_homonimos_municipios_diferentes(municipio_sp, municipio_rj):
    """
    Testa se é possível criar bairros com o mesmo nome, 
    desde que em MUNICÍPIOS DIFERENTES.
    """
    # Cria 'Centro' em São Paulo
    bairro_sp = Bairro.objects.create(nome="CENTRO", municipio=municipio_sp)
    
    # Cria 'Centro' em Campinas (Deve ser permitido)
    bairro_cps = Bairro.objects.create(nome="CENTRO", municipio=municipio_rj)

    assert bairro_sp.id != bairro_cps.id
    assert bairro_sp.nome == bairro_cps.nome
    assert bairro_sp.municipio != bairro_cps.municipio

@pytest.mark.django_db
def test_relacionamento_reverso_bairros(municipio_sp):
    """
    Testa se conseguimos acessar os bairros a partir do objeto Municipio
    (related_name='bairros').
    """
    Bairro.objects.create(nome="MOEMA", municipio=municipio_sp)
    Bairro.objects.create(nome="PINHEIROS", municipio=municipio_sp)

    assert municipio_sp.bairros.count() == 2
    assert municipio_sp.bairros.filter(nome="MOEMA").exists()

@pytest.mark.django_db
def test_protecao_delecao_municipio(municipio_sp):
    """
    Testa o on_delete=models.PROTECT.
    Não deve ser possível apagar um Município se ele tiver Bairros vinculados.
    Isso garante a integridade dos endereços fiscais.
    """
    Bairro.objects.create(nome="LAPA", municipio=municipio_sp)

    # Tentar deletar o município deve falhar
    with pytest.raises(models.ProtectedError):
        municipio_sp.delete()

@pytest.mark.django_db
def test_validacao_tamanho_nome(municipio_sp):
    """
    Testa o max_length=60 do campo nome usando full_clean().
    """
    nome_gigante = "A" * 61  # 61 caracteres
    bairro = Bairro(nome=nome_gigante, municipio=municipio_sp)

    with pytest.raises(ValidationError) as excinfo:
        bairro.full_clean()
    
    assert "nome" in excinfo.value.message_dict