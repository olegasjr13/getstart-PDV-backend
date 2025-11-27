# enderecos/tests/conftest.py
import pytest
from django_tenants.utils import tenant_context
from tenants.models import Tenant, Domain  # Ajuste o import conforme o nome do seu app de tenants

@pytest.fixture(scope="function")
def tenant(db):
    """
    Cria um tenant e seu domínio para uso nos testes.
    O parâmetro 'db' garante que o banco de dados de teste esteja disponível.
    """
    # Criação do Tenant (dispara a criação do Schema no Postgres)
    tenant = Tenant(
        schema_name='tenant_teste',
        cnpj_raiz='12345678000199',
        nome='Empresa de Teste',
        premium_db_alias='default',
        active=True
    )
    tenant.save()

    # Criação do Domínio (necessário para rotas e identificação)
    Domain.objects.create(
        domain='teste.localhost',
        tenant=tenant,
        is_primary=True
    )

    return tenant

@pytest.fixture(autouse=True)
def setup_tenant_context(tenant):
    """
    Fixture mágica (autouse=True):
    Ela roda automaticamente antes de cada teste neste diretório.
    Ativa o schema do tenant criado acima, roda o teste, e depois sai.
    """
    with tenant_context(tenant):
        yield