import pytest
from django.db import transaction 
from django.db.utils import IntegrityError
from enderecos.models.uf_models import UF
from enderecos.models.pais_models import Pais

@pytest.mark.django_db
def test_uf_constraints_unicidade(pais_brasil):
    """
    Verifica se o banco impede duplicidade de Sigla ou Código IBGE.
    Usamos transaction.atomic() para recuperar a conexão após cada erro esperado.
    """
    # 1. Cria o registro original (Sucesso)
    UF.objects.create(sigla="SC", nome="SANTA CATARINA", codigo_ibge="42", pais=pais_brasil)

    # 2. Teste de Duplicidade de SIGLA
    # Envolvemos em atomic() para que o erro não quebre o resto do teste
    with transaction.atomic():
        with pytest.raises(IntegrityError):
            UF.objects.create(
                sigla="SC",  # Repetido!
                nome="OUTRO ESTADO", 
                codigo_ibge="99", 
                pais=pais_brasil
            )
    
    # 3. Teste de Duplicidade de CÓDIGO IBGE
    # Graças ao bloco anterior ter fechado o atomic(), a transação está limpa aqui.
    with transaction.atomic():
        with pytest.raises(IntegrityError):
            UF.objects.create(
                sigla="XX", 
                nome="TESTE IBGE", 
                codigo_ibge="42",
                pais=pais_brasil
            )