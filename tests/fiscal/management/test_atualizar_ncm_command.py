import io
from datetime import date

import pytest
from django.apps import apps
from django.core.management import call_command
from django_tenants.utils import get_tenant_model, schema_context

from fiscal.management.commands import atualizar_ncm as cmd_module

# Precisamos de transação "full" por causa de schema_context + atomic()
pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.usefixtures("two_tenants_with_admins")
def test_atualizar_ncm_cria_atualiza_e_inativa(monkeypatch):
    """
    Cenário:
    - JSON traz 2 NCMs (01012100 e 01012900).
    - No schema do tenant1 já existe 1 NCM '99999999' ativo (que não virá no JSON).
    - Esperado:
        * Criar 2 novos (01012100, 01012900)
        * Inativar '99999999'
    """
    NCM = apps.get_model("fiscal", "NCM")
    Tenant = get_tenant_model()

    # Pega o tenant1 criado pelo fixture two_tenants_with_admins
    tenant1 = Tenant.objects.get(schema_name="99666666000191")

    # Cria NCM antigo dentro do schema do tenant1
    with schema_context(tenant1.schema_name):
        antigo = NCM.objects.create(
            codigo="99999999",
            descricao="NCM antigo",
            ativo=True,
        )

    # JSON de exemplo semelhante ao que o Siscomex devolve
    fake_json = {
        "dataUltimaAlteracao": "2024-10-01",
        "nomenclaturas": [
            {
                "codigo": "01012100",
                "descricao": "Cavalos reprodutores de raça pura",
                "dataInicio": "2017-01-01",
                "dataFim": None,
                "tipoOrgaoAtoIni": "CAMEX",
                "numeroAtoIni": "10",
                "anoAtoIni": "2016",
            },
            {
                "codigo": "01012900",
                "descricao": "Outros cavalos",
                "dataInicio": "2017-01-01",
                "dataFim": None,
                "tipoOrgaoAtoIni": "CAMEX",
                "numeroAtoIni": "11",
                "anoAtoIni": "2016",
            },
        ],
    }

    class FakeResponse:
        def __init__(self, data, status_code=200):
            self._data = data
            self.status_code = status_code

        def raise_for_status(self):
            if self.status_code >= 400:
                raise Exception(f"HTTP {self.status_code}")

        def json(self):
            return self._data

    def fake_get(url, timeout=60):
        # Garante que estamos chamando a URL certa
        assert "nomenclatura/download/json" in url
        return FakeResponse(fake_json)

    # Monkeypatch do requests.get dentro do módulo do comando
    monkeypatch.setattr(cmd_module.requests, "get", fake_get)

    out = io.StringIO()
    # Rodamos o comando apontando explicitamente para o schema do tenant1
    call_command(
        "atualizar_ncm",
        "--schema-name",
        tenant1.schema_name,
        stdout=out,
    )

    # Verificações dentro do schema do tenant1
    with schema_context(tenant1.schema_name):
        ncm1 = NCM.objects.get(codigo="01012100")
        ncm2 = NCM.objects.get(codigo="01012900")

        assert ncm1.descricao == "Cavalos reprodutores de raça pura"
        assert ncm2.descricao == "Outros cavalos"

        # Ativos
        assert ncm1.ativo is True
        assert ncm2.ativo is True

        # Versão da tabela preenchida de forma coerente
        assert ncm1.versao_tabela.startswith("NCM-2024-10-01")
        assert ncm2.versao_tabela.startswith("NCM-2024-10-01")

        # Campos de vigência
        assert ncm1.vigencia_inicio == date(2017, 1, 1)
        assert ncm1.vigencia_fim is None

        # O NCM antigo deve ter sido inativado
        antigo.refresh_from_db()
        assert antigo.ativo is False
        assert antigo.vigencia_fim is not None

    # Opcional: checar se o comando imprimiu o resumo esperado
    output = out.getvalue()
    assert "Criados: 2" in output
    assert "Inativados: 1" in output


@pytest.mark.usefixtures("two_tenants_with_admins")
def test_atualizar_ncm_dry_run_nao_persiste(monkeypatch):
    """
    Verifica se, com --dry-run, nada é persistido no banco
    dentro do schema do tenant1.
    """
    NCM = apps.get_model("fiscal", "NCM")
    Tenant = get_tenant_model()

    tenant1 = Tenant.objects.get(schema_name="99666666000191")

    fake_json = {
        "dataUltimaAlteracao": "2024-10-01",
        "nomenclaturas": [
            {
                "codigo": "01012100",
                "descricao": "Cavalos reprodutores de raça pura",
                "dataInicio": "2017-01-01",
                "dataFim": None,
            },
        ],
    }

    class FakeResponse:
        def __init__(self, data, status_code=200):
            self._data = data
            self.status_code = status_code

        def raise_for_status(self):
            if self.status_code >= 400:
                raise Exception(f"HTTP {self.status_code}")

        def json(self):
            return self._data

    def fake_get(url, timeout=60):
        return FakeResponse(fake_json)

    monkeypatch.setattr(cmd_module.requests, "get", fake_get)

    out = io.StringIO()

    # Garante que não há NCM antes
    with schema_context(tenant1.schema_name):
        assert NCM.objects.count() == 0

    call_command(
        "atualizar_ncm",
        "--schema-name",
        tenant1.schema_name,
        "--dry-run",
        stdout=out,
    )

    # Depois do dry-run continua sem registros
    with schema_context(tenant1.schema_name):
        assert NCM.objects.count() == 0

    output = out.getvalue()
    assert "DRY-RUN habilitado" in output
