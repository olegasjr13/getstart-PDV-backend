# Guia Prático de Multi-Tenancy — GetStart PDV Backend

## 1. Objetivo

Este documento explica **como o multi-tenant está implementado na prática** no backend GetStart PDV e define os padrões que TODO novo desenvolvimento deve seguir.

Ele responde às perguntas:

- Como o backend decide **qual tenant (empresa) está atendendo** em cada requisição?
- O que mora no **schema público** vs. **schema de cada tenant**?
- Como **provisionar** um novo tenant via API?
- Como escrever **código, scripts e testes** que respeitem multi-tenancy (sem vazar dado de um tenant para outro)?

> Este guia complementa:
>
> - `docs/arquitetura/overview.md`
> - `docs/arquitetura/dominios.md`
> - `docs/backend/guia_setup_dev.md`
> - `docs/backend/padroes_backend.md`

---

## 2. Visão Geral da Arquitetura Multi-Tenant

### 2.1 Modelo: schema por tenant (PostgreSQL + django-tenants)

Usamos **PostgreSQL** com **`django_tenants`** e o padrão **schema-per-tenant**:

- Um único banco físico (`pdvdados` em dev).
- Múltiplos schemas:
  - `public` → schema público.
  - `12345678000199` → exemplo de schema de tenant (CNPJ raiz).
  - `...` → outros schemas, um por tenant.

Configuração principal em `config/settings.py`:

```python
DATABASES = {
    "default": {
        "ENGINE": "django_tenants.postgresql_backend",
        "NAME": os.getenv("PGDATABASE","pdvdados"),
        "USER": os.getenv("PGUSER","postgres"),
        "PASSWORD": os.getenv("PGPASSWORD","29032013"),
        "HOST": os.getenv("PGHOST","127.0.0.1"),
        "PORT": os.getenv("PGPORT","5432"),
        "TEST": {
            "NAME": "test_pdvdados",
        },
    }
}

DATABASE_ROUTERS = (
    "django_tenants.routers.TenantSyncRouter",
)
```

### 2.2 Tenant e Domain

Os modelos de tenant estão no app `tenants`:

```python
from django_tenants.models import TenantMixin, DomainMixin

class Tenant(TenantMixin):
    cnpj_raiz = models.CharField(max_length=14, unique=True)  # X-Tenant-ID
    nome = models.CharField(max_length=150)
    premium_db_alias = models.CharField(max_length=64, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    auto_create_schema = True

class Domain(DomainMixin):
    pass
```

Pontos importantes:

- `Tenant.schema_name` identifica o schema (ex.: `"12345678000199"`).
- `Tenant.cnpj_raiz` é o identificador de negócio do tenant e normalmente coincide com `schema_name`.
- `Domain.domain` (ex.: `cliente-demo.localhost`) é usado para resolver o tenant a partir do **Host** da requisição.

Configuração em `settings.py`:

```python
TENANT_MODEL = "tenants.Tenant"
TENANT_DOMAIN_MODEL = "tenants.Domain"
```

### 2.3 SHARED_APPS vs TENANT_APPS

Separação de apps por schema:

```python
# apps que moram no PUBLIC schema (mínimo)
SHARED_APPS = (
    "django_tenants",
    "django.contrib.contenttypes",
    # nada de auth/admin/sessions aqui
    "tenants",   # gerenciamento de tenants/domínios via API
    "commons",   # health/time endpoints
)

# apps que moram nos schemas de cada tenant
TENANT_APPS = (
    "django.contrib.contenttypes",        # precisa repetir
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.admin",

    "rest_framework",
    "rest_framework.authtoken",
    "drf_spectacular",

    "usuario",   # AUTH_USER_MODEL
    "filial",
    "terminal",
    "fiscal",
    # demais apps nas próximas sprints: produto, caixa, etc.
)

INSTALLED_APPS = list(SHARED_APPS) + [a for a in TENANT_APPS if a not in SHARED_APPS]
```

**Regra prática:**

- Tudo que é **global** e não carrega dados de negócio de um tenant específico (ex.: healthcheck, criação de tenant) → `SHARED_APPS` → schema `public`.
- Tudo que é **dado de negócio** (usuário, filial, terminal, NFC-e, etc.) → `TENANT_APPS` → schemas dos tenants.

---

## 3. Como o tenant é resolvido em runtime

### 3.1 Middleware principal

Em `MIDDLEWARE`:

```python
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django_tenants.middleware.main.TenantMainMiddleware",  # <- resolve o tenant
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    ...
]
```

O `TenantMainMiddleware` faz:

1. Lê o **Host** da requisição (`HTTP_HOST`).
2. Busca um `Domain` com `domain=<host>`.
3. Ativa o schema correspondente ao `tenant` ligado a esse `Domain`.
4. Carrega os apps de `TENANT_APPS` naquele schema.

### 3.2 Host e Domain

Exemplo de bootstrap usado nos testes fiscais:

```python
TENANT_SCHEMA = "12345678000199"
TENANT_HOST = "cliente-demo.localhost"

def _bootstrap_public_tenant_and_domain():
    Tenant = get_tenant_model()
    Domain = apps.get_model("tenants", "Domain")
    Tenant.objects.get_or_create(
        schema_name="public",
        defaults=dict(cnpj_raiz="00000000000000", nome="PUBLIC", premium_db_alias=None),
    )
    ten, _ = Tenant.objects.get_or_create(
        schema_name=TENANT_SCHEMA,
        defaults=dict(cnpj_raiz=TENANT_SCHEMA, nome="Tenant Teste", premium_db_alias=None),
    )
    dom, created_dom = Domain.objects.get_or_create(
        domain=TENANT_HOST, defaults=dict(tenant=ten, is_primary=True)
    )
    ...
```

E o `APIClient` de teste:

```python
client = APIClient()
client.defaults["HTTP_HOST"] = TENANT_HOST
client.defaults["HTTP_X_TENANT_ID"] = TENANT_SCHEMA  # usado só para rastreio/consistência
```

**Na prática:**

- Em produção, o **Host** (ex.: `empresaX.getstartpdv.com.br`) é o que define qual tenant está ativo.
- O header `X-Tenant-ID` é usado nos testes para reforçar a identificação e pode ser usado para logging/auditoria, mas quem manda é o **Host** + `Domain`.

---

## 4. Provisão de novos tenants via API

### 4.1 Endpoint de provisionamento público

No `config/urls_public.py` (schema `public`):

```python
from django.urls import path, include

urlpatterns = [
    path("api/v1/", include("commons.urls")),
    path("api/v1/", include("tenants.urls")),
]
```

Em `tenants/urls.py`:

```python
from django.urls import path
from .views.tenants_views import criar_tenant

urlpatterns = [
    path("tenants", criar_tenant),  # POST /api/v1/tenants
]
```

### 4.2 Segurança: token de provisionamento

Permissão em `tenants/permissions.py`:

```python
class PublicProvisioningPermission(BasePermission):
    """Permite provisionamento de tenant via token estático de ambiente.

    Aceita X-Admin-Token ou X-Tenant-Provisioning-Token no header.
    Compara com ADMIN_PROVISIONING_TOKEN ou TENANT_PROVISIONING_TOKEN do settings.
    """

    def has_permission(self, request, view):
        header_token = (
            request.headers.get("X-Admin-Token")
            or request.headers.get("X-Tenant-Provisioning-Token")
        )
        env_token = (
            getattr(settings, "ADMIN_PROVISIONING_TOKEN", None)
            or getattr(settings, "TENANT_PROVISIONING_TOKEN", None)
        )
        return bool(header_token and env_token and header_token == env_token)
```

Variáveis em `settings.py`:

```python
TENANT_PROVISIONING_TOKEN = os.getenv("TENANT_PROVISIONING_TOKEN", "")
ADMIN_PROVISIONING_TOKEN  = os.getenv("ADMIN_PROVISIONING_TOKEN", "")
```

**Regra prática:**

- Para criar um tenant via API, é obrigatório enviar:
  - `X-Admin-Token` **ou** `X-Tenant-Provisioning-Token`
  - Com valor igual ao configurado no ambiente.

### 4.3 Payload e fluxo de criação

Serializer em `tenants/serializers.py`:

```python
class TenantCreateSerializer(serializers.Serializer):
    cnpj_raiz = serializers.RegexField(regex=r"^\d{14}$")
    nome = serializers.CharField(max_length=150)
    domain = serializers.CharField(max_length=255)
    premium_db_alias = serializers.CharField(
        max_length=64, required=False, allow_null=True, allow_blank=True
    )
```

Fluxo esperado em `tenants/views/tenants_views.py` (trecho intermediário omitido no snapshot, mas comportamento claro):

1. Valida o payload.
2. Cria o `Tenant` com `cnpj_raiz` e `schema_name` (geralmente igual ao CNPJ).
3. Executa migrações para esse schema (via `call_command`, ex.: `migrate_schemas`).
4. Cria um `Domain` apontando `domain` para o `tenant` recém-criado.

Resposta:

```python
return Response(
    {"tenant": tenant.cnpj_raiz, "schema": tenant.schema_name},
    status=status.HTTP_201_CREATED,
)
```

**Recomendação de uso em dev:**

- Em dev/local, você pode:
  - Criar tenant via `POST /api/v1/tenants` (usando os tokens de provisionamento), **ou**
  - Criar manualmente via `schema_context` nos testes, como já ocorre nos testes fiscais.

---

## 5. Como escrever código multi-tenant-safe

### 5.1 Regra de ouro

> **Nunca** escrever código que faça query em dados de negócio sem estar no contexto de um tenant.

Na aplicação web (requisições HTTP), o `TenantMainMiddleware` já cuida disso com base no Host.  
Só não vale “burlar” esse mecanismo.

### 5.2 Onde colocar os modelos

- Modelos que dependem de tenant (usuário, filial, terminal, NFC-e, caixa, etc.) → apps que estão em `TENANT_APPS`.
- Nada de colocar modelos de negócio em `SHARED_APPS`.

### 5.3 Comandos de management e scripts

Para rodar lógica que atinge um ou mais tenants, usar sempre `schema_context`:

```python
from django_tenants.utils import schema_context, get_tenant_model

Tenant = get_tenant_model()

for tenant in Tenant.objects.exclude(schema_name="public"):
    with schema_context(tenant.schema_name):
        # aqui você está dentro do schema do tenant
        # pode acessar Usuario, Filial, Fiscal, etc.
        processar_alguma_coisa(tenant)
```

**Padrão para novos management commands:**

- Usar `get_tenant_model()` para iterar nos tenants.
- Ignorar `schema_name="public"` (exceto comandos específicos para público).
- Envolver cada iteração em `schema_context(tenant.schema_name)`.

### 5.4 Background jobs, tarefas assíncronas, workers

Mesmo padrão:

- A payload da tarefa deve carregar o `tenant_schema` ou `tenant_id`.
- A primeira coisa dentro do worker deve ser:

```python
with schema_context(tenant_schema):
    # rodar lógica aqui
```

---

## 6. Testes multi-tenant

O módulo fiscal já possui uma **bateria de testes multi-tenant** muito boa, que serve como referência.

Exemplo de padrões usados em testes como `fiscal/tests/test_nfce_multitenant_isolation.py`:

1. Bootstrap de tenants e domain (função `_bootstrap_public_tenant_and_domain`).
2. Criação de `APIClient` configurado com:
   - `HTTP_HOST = TENANT_HOST`
   - Autenticação JWT
   - (Opcionalmente) `HTTP_X_TENANT_ID = TENANT_SCHEMA`

```python
client = APIClient()
client.defaults["HTTP_HOST"] = TENANT_HOST
client.defaults["HTTP_X_TENANT_ID"] = TENANT_SCHEMA
```

3. Execução de chamadas fiscais (`/api/v1/fiscal/nfce/...`) para garantir que:
   - Dados de um tenant não aparecem no outro.
   - Sequências de numeração são isoladas por tenant/filial/terminal/série.

**Recomendação:**

- Para qualquer novo domínio multi-tenant sensível (ex.: caixa, sync), siga esse padrão de testes:
  - Criar pelo menos **2 tenants**.
  - Executar o mesmo fluxo nos dois.
  - Garantir que não há vazamento de dados entre eles.

---

## 7. Migrations e evolução de schema

### 7.1 Onde rodar migrations

Com `django_tenants`, as migrations são aplicadas:

- No schema `public` para `SHARED_APPS`.
- Em todos os schemas de tenants para `TENANT_APPS`.

Ao criar novos apps de negócio:

- Adicionar o app a `TENANT_APPS`.
- Garantir que as migrations rodam de forma segura para:
  - tenants novos (schema recém-criado),
  - tenants já existentes (schemas antigos).

### 7.2 Boas práticas para migrations multi-tenant

- Evitar migrations destrutivas sem passos intermediários (ex.: remover coluna usada em produção).
- Quando for necessário:
  - Usar estratégia de **migrations compatíveis**:
    - 1ª migration: adicionar coluna nova, manter antiga.
    - Atualizar código para usar a nova coluna.
    - 2ª migration: remover coluna antiga.
- Sempre que introduzir constraint forte (unique, foreign key), validar em **todos tenants** em ambiente de staging antes de subir em produção.

---

## 8. Segurança e isolamento

### 8.1 Garantias básicas

- Cada tenant tem seu próprio schema → queries não atravessam tenants por acidente.
- A escolha do schema é feita com base no **Host** (Domain) → um request HTTP sempre opera em um único tenant lógico.

### 8.2 Coisas a evitar

- Consultas em `Tenant` ou `Domain` dentro de views de negócio (salvo endpoints especificamente administrativos).
- Lógica que tenta “forçar” tenant por ID/UUID sem usar `schema_context`.
- Usar caches globais sem incluir `tenant_schema` na chave (para camadas de cache futuras).

---

## 9. Checklist para novas features multi-tenant

Antes de subir qualquer feature que envolva multi-tenancy, validar:

1. **Modelos**:
   - Estão em um app de `TENANT_APPS`?
   - Não dependem de dados de outro tenant?

2. **Views/Services**:
   - Não fazem queries diretas em `Tenant`/`Domain` para dados de negócio.
   - Dependem da resolução de tenant feita pelo middleware.

3. **Scripts/Comandos**:
   - Usam `get_tenant_model()` + `schema_context`.
   - Ignoram `public` quando não faz sentido.

4. **Testes**:
   - Pelo menos um teste com **2 tenants** validando isolamento.
   - Testes usando `HTTP_HOST` adequado.

5. **Logs/Auditoria**:
   - Logs de eventos relevantes devem incluir:
     - `tenant_schema` ou `tenant_id`
     - `cnpj_raiz` (quando aplicável)
   - Ver `docs/observabilidade/logbook_eventos.md` e `docs/observabilidade/padroes_logs_backend.md`.

---

Seguindo esses padrões, qualquer dev backend consegue trabalhar no projeto sem medo de quebrar multi-tenancy ou vazar dados entre empresas, e a arquitetura se mantém consistente com o que já está implementado hoje no código do GetStart PDV.
