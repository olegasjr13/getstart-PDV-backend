
---

# 📗 **DOCUMENTO 2 — `docs/qa/guia_testes_backend.md` (COMPLETO E ROBUSTO)**

---

```markdown
# Guia de Testes Backend — GetStart PDV

## 1. Objetivo

Este documento define o padrão oficial de testes para o backend GetStart PDV, incluindo:

- Estrutura de testes
- Testes multi-tenant
- Testes fiscais
- Boas práticas
- Padronização aplicada no projeto atual

---

# 2. Frameworks e Ferramentas

O backend usa:

- **pytest**
- **pytest-django**
- **DRF APIClient**
- **django-tenants schema_context**
- **FactoryBoy (opcional futuro)**

`pytest.ini`:

```ini
[pytest]
DJANGO_SETTINGS_MODULE = config.settings
python_files = test_*.py *_tests.py
3. Estrutura de Testes

Conforme padrão atual do projeto:

fiscal/
└── tests/
    ├── test_nfce_reserva.py
    ├── test_nfce_idempotencia_mesmo_request_id.py
    ├── test_nfce_multitenant_isolation.py
    └── ...


Cada app deve conter:

app/tests/test_xxx.py

4. Criando Tenant para Testes

Todos os testes multi-tenant devem seguir o padrão encontrado no projeto:

from django_tenants.utils import schema_context, get_tenant_model
from django.apps import apps

Tenant = get_tenant_model()
Domain = apps.get_model("tenants", "Domain")

tenant, _ = Tenant.objects.get_or_create(
    schema_name="12345678000199",
    defaults=dict(cnpj_raiz="12345678000199", nome="Tenant Teste")
)

Domain.objects.get_or_create(
    domain="tenant-test.localhost",
    defaults=dict(tenant=tenant, is_primary=True)
)

Acesso ao tenant no teste:
client.defaults["HTTP_HOST"] = "tenant-test.localhost"
client.defaults["HTTP_X_TENANT_ID"] = "12345678000199"

5. Testes Fiscais (padrão oficial)

O módulo fiscal tem a melhor referência do projeto.

5.1 Teste de reserva

Valida:

criação de número

idempotência

estrutura de retorno

5.2 Teste de idempotência

Exemplo real:

resp1 = client.post(url, payload)
resp2 = client.post(url, payload)
assert resp2.data["numero"] == resp1.data["numero"]

5.3 Teste completo multi-tenant

Garantir que:

Tenant A possui sequência A

Tenant B possui sequência B

Sem interferência

5.4 Teste do fluxo completo

Garantir:

reserva → pre → emissão

6. Testes Multi-Tenant (obrigatórios)
6.1 Sempre usar host
client.defaults["HTTP_HOST"] = TENANT_HOST

6.2 Sempre criar 2 tenants para isolação
tenantA
tenantB

6.3 Sempre testar independência dos tenants:

Numeração

Pré-emissão

Emissão

Caixa (futuro)

Sync/outbox (futuro)

7. Boas práticas obrigatórias

✔️ Nomear arquivos como test_<funcionalidade>.py
✔️ Views testadas por integração
✔️ Services testados com unit tests
✔️ Testes de erro SEMPRE que existir regra fiscal
✔️ Sempre testar idempotência quando existir request_id
✔️ Sempre testar com dois tenants quando envolver dados de negócio

8. Comandos para executar os testes
pytest
pytest fiscal/tests/
pytest fiscal/tests/test_nfce_multitenant_isolation.py

9. Conclusão

Este guia define como TODO teste backend do GetStart PDV deve ser escrito.
O padrão atual do módulo fiscal é o modelo oficial para todo o projeto.
