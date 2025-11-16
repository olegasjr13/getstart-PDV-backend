# Healthchecks da API — GetStart PDV

## 1. Objetivo

Este documento define os **endpoints oficiais de healthcheck** do backend do GetStart PDV, usados para:

- Monitoramento (DevOps, Observabilidade)
- Orquestradores (Docker, Kubernetes, Railway etc.)
- Diagnóstico rápido de problemas
- Integração com ferramentas externas (uptime, alarmes)
- Comportamento padrão para POS Controle-like

---

# 2. Tipos de Healthcheck

Serão expostos pelo backend, no mínimo, dois tipos:

1. **Liveness**  → verifica se o processo está vivo.
2. **Readiness** → verifica se o backend está pronto para atender requisições.

---

# 3. Endpoint de Liveness

### 3.1. URL

```http
GET /health/liveness
```

### 3.2. Objetivo

Responder se a aplicação **está viva**, ou seja:

- Processo do backend está rodando.
- Thread principal está respondendo.

Não faz checagens profundas (DB, SEFAZ etc.).

### 3.3. Resposta esperada

**Status HTTP:** `200 OK`

```json
{
  "status": "ok",
  "service": "getstart-pdv-backend",
  "check": "liveness"
}
```

Em caso de erro grave (por exemplo, exceção inesperada no handler), retornar:

**Status HTTP:** `500`

```json
{
  "status": "error",
  "service": "getstart-pdv-backend",
  "check": "liveness"
}
```

### 3.4. Uso típico

- Kubernetes: `livenessProbe`
- Docker: `HEALTHCHECK`
- Uptime bots (simples)

---

# 4. Endpoint de Readiness

### 4.1. URL

```http
GET /health/readiness
```

### 4.2. Objetivo

Responder se o backend está **pronto para operar**, verificando:

- Conexão com banco de dados.
- Migrações aplicadas.
- Acessibilidade básica de tenants.
- Integrações críticas (opcional, ex.: SEFAZ, filas, cache).

### 4.3. Estrutura da resposta

**Status HTTP:** `200 OK` (quando tudo OK)
**Status HTTP:** `503 Service Unavailable` (quando algum check falhar)

Resposta JSON:

```json
{
  "status": "ok" | "degraded" | "error",
  "service": "getstart-pdv-backend",
  "check": "readiness",
  "components": {
    "database": {
      "status": "ok" | "error",
      "details": "..."
    },
    "migrations": {
      "status": "ok" | "error",
      "details": "..."
    },
    "tenants": {
      "status": "ok" | "error",
      "details": "..."
    },
    "sefaz": {
      "status": "ok" | "degraded" | "skipped",
      "details": "..."
    }
  }
}
```

---

# 5. Checks mínimos do Readiness

## 5.1. Banco de Dados

- Verifica se consegue executar uma query simples:
  - `SELECT 1` ou equivalente via ORM.

Caso falhe:

- `components.database.status = "error"`
- `status geral = "error"`
- HTTP = `503`

---

## 5.2. Migrações

Opcional mas recomendado:

- Verificar se não há migrações pendentes críticas.
- Podem ser checadas:
  - Na inicialização da aplicação.
  - Periodicamente em background.

Em caso de migrações pendentes críticas:

- `components.migrations.status = "error"` ou `"degraded"` dependendo da política.

---

## 5.3. Tenants

Pode ser feita uma verificação simples:

- Buscar um tenant padrão.
- Validar se o schema existe.
- Validar se o contexto multi-tenant está funcional.

Falhas:

- `components.tenants.status = "error"`
- HTTP = `503` (se crítico)

---

## 5.4. SEFAZ (opcional / configurável)

Para ambientes que exigem cheque de SEFAZ:

- Fazer um teste superficial:
  - Checar apenas se o host é resolvível.
  - Ou pingar um endpoint de status (quando houver).

Nos ambientes onde SEFAZ não deve ser checada (dinâmica ou frequente):

- Retornar:
  - `status = "skipped"`
  - `details = "check disabled"`

---

# 6. Lógica de Status Geral

A regra geral para o campo `status` no readiness:

- `ok` → todos os componentes críticos OK.
- `degraded` → pelo menos um componente **não crítico** com problema.
- `error` → qualquer componente **crítico** com problema.

**Componentes críticos:**

- `database`
- `migrations` (quando configurado como obrigatório)
- `tenants`

**Componentes opcionais/dependendo do ambiente:**

- `sefaz`
- `cache`
- `fila`

---

# 7. Logs de Healthcheck

Para não poluir logs:

- Liveness/readiness devem ser logados no máximo em nível `DEBUG`.
- Podem ser totalmente ignorados pelos handlers de acesso (excluir path `/health/*`).

Quando um check falhar, é recomendado:

- Gerar log em `WARNING` ou `ERROR`.
- Exemplo de evento: `health_readiness_check`.

---

# 8. Integração com Observabilidade

Os endpoints podem ser consumidos por:

- Prometheus (via blackbox export)
- Zabbix / Grafana / Datadog / etc.
- Railway / Render / plataformas PaaS

Recomendado:

- Configurar alertas quando:
  - `/health/readiness` retornar `503` repetidas vezes.
  - Tempo de resposta desses endpoints ultrapassar um limite.

---

# 9. Exemplos de Respostas

### 9.1. Tudo OK

```json
{
  "status": "ok",
  "service": "getstart-pdv-backend",
  "check": "readiness",
  "components": {
    "database": {
      "status": "ok",
      "details": "connected"
    },
    "migrations": {
      "status": "ok",
      "details": "up_to_date"
    },
    "tenants": {
      "status": "ok",
      "details": "context loaded"
    },
    "sefaz": {
      "status": "skipped",
      "details": "check disabled in this environment"
    }
  }
}
```

### 9.2. Banco de dados offline

```json
{
  "status": "error",
  "service": "getstart-pdv-backend",
  "check": "readiness",
  "components": {
    "database": {
      "status": "error",
      "details": "connection refused"
    },
    "migrations": {
      "status": "ok",
      "details": "up_to_date"
    },
    "tenants": {
      "status": "error",
      "details": "cannot load schema without database"
    },
    "sefaz": {
      "status": "skipped",
      "details": "not checked"
    }
  }
}
```

HTTP: `503 Service Unavailable`

---

# 10. Segurança dos Healthchecks

- Endpoints `/health/liveness` e `/health/readiness` **podem ser públicos** (geralmente não exigem autenticação).
- Se necessário, podem ser restritos por:
  - IP (firewall, proxy)
  - Camada externa (NGINX, API Gateway)

**Nunca** devem expor:

- Senhas
- Strings de conexão
- Stack trace
- Dados sensíveis de tenants

---

# 11. Resumo das URLs

- `GET /health/liveness`
  - Simples, retorno rápido.
  - Usado para saber se o processo está vivo.

- `GET /health/readiness`
  - Componente crítico.
  - Checa dependências essenciais antes de considerar o backend “pronto”.

---

# 12. Conclusão

Com estes endpoints padronizados:

- DevOps consegue monitorar o backend de forma robusta.
- O POS sabe quando o backend está realmente pronto.
- QA pode validar estados de infraestrutura em cenários de teste.
- Logs e alertas podem ser configurados de forma previsível.

Qualquer alteração de infraestrutura crítica deve atualizar este documento.
