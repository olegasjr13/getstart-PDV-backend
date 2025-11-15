# Logbook Oficial de Eventos — GetStart PDV
Versão: 1.0
Responsável: Arquitetura Backend

---

# 1. Objetivo
Este documento registra **todos os eventos operacionais, fiscais, técnicos e de segurança** do GetStart PDV.
Ele serve como referência única para:

- observabilidade (logs + Sentry + dashboards)
- auditoria fiscal
- rastreabilidade multi-tenant
- detecção de falhas
- diagnóstico de problemas do PDV ou backend
- alinhamento entre times (backend, mobile, QA, fiscal, auditoria)

Cada evento aqui documentado possui:

- **Descrição funcional**
- **Origem (service/view/task)**
- **Payload mínimo**
- **Campos obrigatórios**
- **Severidade**
- **Relacionamento com XML/NFC-e** (quando aplicável)
- **Exemplos REAIS, baseados no que o projeto já faz**

---

# 2. Estrutura Geral dos Eventos

Todos os eventos seguem o padrão:

```json
{
  "timestamp": "2025-01-05T12:00:15.123Z",
  "event": "nome_do_evento",
  "level": "INFO",
  "service": "fiscal",
  "tenant": "12345678000199",
  "schema": "t_12345678000199",
  "filial": "FILIAL-001",
  "terminal": "T1",
  "request_id": "UUID",
  "user_id": 42,
  "payload": {...}
}
```

---

# 3. Logbook por Módulo

A seguir, todos os eventos **oficiais, padronizados e obrigatórios**.

---

# 3.1 Módulo Fiscal (NFC-e)

## 3.1.1 Evento: fiscal_reserva_criada

**Quando ocorre:**
Após execução bem-sucedida do `NfceNumeroService.reservar()`.

**Nível:** INFO
**Origem:** `services/numero_service.py`

**Campos obrigatórios:**
- numero
- serie
- filial
- terminal
- request_id

**Exemplo realista:**

```json
{
  "event": "fiscal_reserva_criada",
  "service": "fiscal",
  "level": "INFO",
  "tenant": "12345678000199",
  "schema": "t_12345678000199",
  "filial": "A1",
  "terminal": "T1",
  "request_id": "abc-123",
  "payload": {
    "numero": 1029,
    "serie": 1
  }
}
```

---

## 3.1.2 Evento: fiscal_pre_emissao_registrada

**Quando ocorre:**
Após `NfcePreEmissaoService.criar_pre_emissao()` consolidar itens/pagamentos.

**Nível:** INFO
**Campos obrigatórios:**
- numero
- serie
- valor_total
- quantidade_itens

**Exemplo realista:**

```json
{
  "event": "fiscal_pre_emissao_registrada",
  "service": "fiscal",
  "level": "INFO",
  "tenant": "12345678000199",
  "filial": "A1",
  "terminal": "T1",
  "request_id": "abc-123",
  "payload": {
    "numero": 1029,
    "serie": 1,
    "itens": 3,
    "valor_total": 120.5
  }
}
```

---

## 3.1.3 Evento: fiscal_emitida_mock

**Quando ocorre:**
Após emissão mock gerar XML + protocolo.

**Nível:** INFO
**Origem:** `services/emissao_service.py`

**Campos obrigatórios:**
- chave
- protocolo
- numero
- serie

**Exemplo realista:**

```json
{
  "event": "fiscal_emitida_mock",
  "service": "fiscal",
  "level": "INFO",
  "tenant": "12345678000199",
  "filial": "A1",
  "terminal": "T1",
  "request_id": "abc-123",
  "payload": {
    "chave": "35191112345678000199550010000010291000010290",
    "protocolo": "987654321",
    "numero": 1029,
    "serie": 1
  }
}
```

---

## 3.1.4 Evento: fiscal_cancelada (futuro)

Emissão da carta de correção + cancelamento SEFAZ real.

---

# 3.2 Módulo de Autenticação (Auth)

## 3.2.1 auth_login_success

**Quando ocorre:** login normal.
**Nível:** INFO

Campos obrigatórios:
- user_id
- perfil
- tenant

Exemplo:

```json
{
  "event": "auth_login_success",
  "service": "auth",
  "level": "INFO",
  "user_id": 12,
  "tenant": "12345678000199",
  "payload": {
    "perfil": "OPERADOR"
  }
}
```

---

## 3.2.2 auth_login_failed

**Quando ocorre:** falha por senha inválida.

Nível: WARNING (não ERROR)

---

## 3.2.3 auth_refresh

Em cada refresh token válido.

---

# 3.3 Módulo Multi-Tenant

## 3.3.1 tenant_context_loaded

**Quando ocorre:**
Middleware carrega tenant + schema.

Nível: INFO
Campos obrigatórios:
- domain
- resolved_schema

---

## 3.3.2 tenant_schema_mismatch_warning

**Quando ocorre:**
Host e X-Tenant-ID não correspondem.

Nível: WARNING

---

# 3.4 Módulo Catálogo

## 3.4.1 catalogo_sync_enviado

VGeral desde `/catalogo/produtos/sync`.

---

# 3.5 Módulo Caixa

## 3.5.1 caixa_aberto

Campos:
- saldo_inicial
- operador_id

## 3.5.2 caixa_fechado

Campos:
- saldo_final
- divergencias

---

# 4. Severidade dos Eventos

| Severidade | Quando usar |
|------------|-------------|
| INFO | Fluxo normal |
| WARNING | Anomalia, tentativa inválida |
| ERROR | Falha tratada |
| CRITICAL | Falha que compromete o fiscal ou integridade |

---

# 5. Eventos Obrigatórios Fiscais (Auditoria)

Todos os eventos abaixo são obrigatórios por lei de rastreabilidade:

1. **fiscal_reserva_criada**
2. **fiscal_pre_emissao_registrada**
3. **fiscal_emitida_mock / fiscal_emitida_sefaz**
4. **fiscal_cancelada** (futuro)

---

# 6. Correlação Entre Eventos (Tracing)

A correlação segue:

```
request_id → reserva → pré → emissão → integração externa (futuro)
```

Cada evento deve carregar:
- request_id
- numero
- serie

Assim é possível reconstruir toda a transação fiscal apenas pelos logs.

---

# 7. Conclusão

Este logbook define todos os eventos oficiais do sistema e deve ser seguido estritamente.
Qualquer nova funcionalidade deve registrar eventos conforme este padrão.
