# Guia de Erros e Exceções — GetStart PDV (API Backend)

## 1. Objetivo

Este documento define o **padrão oficial de erros, códigos, formatos e exceções** usados no backend do GetStart PDV.
Ele garante:

- Consistência entre módulos (fiscal, vendas, auth, multi-tenant)
- Integração perfeita com o app POS (que não usa navegador)
- Fácil depuração e monitoramento (Sentry + logs JSON)
- Padrão unificado para QA automatizado
- Mapeamento SEFAZ → API (NFC-e)
- Segurança (evitando vazar stack trace ou dados sensíveis)

---

# 2. Formato Padrão de Erros (API REST)

Todas as respostas de erro **devem retornar o seguinte formato**:

```json
{
  "error": "<CODIGO_DO_ERRO>",
  "message": "<mensagem_legivel>",
  "details": { ... },   // opcional
  "request_id": "<uuid>"
}
```

### 2.1. Campos obrigatórios

| Campo | Descrição |
|-------|-----------|
| `error` | Código único do erro (ver seções abaixo) |
| `message` | Mensagem clara para o app POS |
| `request_id` | Correlação completa com logs e auditoria |

### 2.2. Campos opcionais

| Campo | Uso |
|-------|-----|
| `details` | Dados adicionais úteis para debugging |
| `field_errors` | Para validação de payload (HTTP 400) |

---

# 3. Estrutura de Códigos de Erro

Os códigos seguem este padrão:

```
<MÓDULO>_<CATEGORIA><NUMERO>
```

### Exemplos reais:

```
AUTH_4001      → Credenciais inválidas
TENANT_4002    → Tenant inativo
FISCAL_5001    → Falha de comunicação com SEFAZ
FISCAL_4007    → Certificado A1 inválido
VALID_4000     → Campos inválidos
```

---

# 4. Categorias Oficiais

| Categoria | Significado |
|----------|-------------|
| **4000** | Erros de validação / negócio |
| **5000** | Erros internos / externos (SEFAZ, infraestrutura) |
| **7000** | Erros específicos do POS/coleta/terminal (opcional) |

---

# 5. Códigos por Módulo

A seguir os códigos oficiais por módulo.

---

# 5.1. AUTH (Autenticação)

| Código | HTTP | Descrição |
|--------|------|------------|
| `AUTH_4001` | 401 | Credenciais inválidas |
| `AUTH_4002` | 403 | Usuário sem permissão para a filial/terminal |
| `AUTH_4003` | 403 | Tenant inativo |
| `AUTH_4004` | 403 | Token expirado |
| `AUTH_5001` | 500 | Erro inesperado no processo de login |

---

# 5.2. TENANT (Multi-tenant)

| Código | HTTP | Descrição |
|--------|------|------------|
| `TENANT_4001` | 400 | Header `X-Tenant-ID` ausente |
| `TENANT_4002` | 403 | Tenant inativo |
| `TENANT_4003` | 404 | Tenant não encontrado |
| `TENANT_5001` | 500 | Falha ao carregar o schema do tenant |

---

# 5.3. VALID (Validação Geral)

| Código | HTTP | Descrição |
|--------|------|------------|
| `VALID_4000` | 400 | Validação de payload inválida |
| `VALID_4001` | 400 | Campo obrigatório ausente |
| `VALID_4002` | 400 | Formato inválido |
| `VALID_4003` | 400 | Tipo incorreto |
| `VALID_4004` | 400 | Requisição malformada |

Exemplo de resposta:

```json
{
  "error": "VALID_4000",
  "message": "Dados inválidos.",
  "field_errors": {
    "valor_total": ["Deve ser maior que zero."]
  },
  "request_id": "..."
}
```

---

# 5.4. FISCAL (NFC-e, SEFAZ, XML)

## 5.4.1. Erros de negócio (4000)

| Código | HTTP | Descrição |
|--------|------|------------|
| `FISCAL_4001` | 400 | Filial sem ambiente configurado |
| `FISCAL_4002` | 400 | Certificado A1 inválido ou vencido |
| `FISCAL_4003` | 400 | Terminal inativo |
| `FISCAL_4004` | 400 | Número da NFC-e inválido |
| `FISCAL_4005` | 400 | Pré-emissão não encontrada |
| `FISCAL_4006` | 409 | Número já utilizado (idempotência) |
| `FISCAL_4007` | 400 | Payload de venda inválido |
| `FISCAL_4008` | 400 | Série não permitida |
| `FISCAL_4009` | 400 | UF da filial não suportada no MVP |

---

## 5.4.2. Erros de integração (5000)

| Código | HTTP | Descrição |
|--------|------|------------|
| `FISCAL_5001` | 502 | Falha de comunicação com SEFAZ |
| `FISCAL_5002` | 500 | XML inválido (schema) |
| `FISCAL_5003` | 500 | Falha na assinatura do XML |
| `FISCAL_5004` | 500 | Retorno SEFAZ malformado |
| `FISCAL_5005` | 500 | Timeout SEFAZ |
| `FISCAL_5006` | 500 | Erro inesperado no client SEFAZ |

---

## 5.4.3. Erros decorrentes da SEFAZ (rejeições)

### Sempre retornam:

- HTTP 409 (conflito)
- `error = FISCAL_400x`
- Mensagem contendo o código da rejeição SEFAZ

Exemplo:

```json
{
  "error": "FISCAL_4007",
  "message": "Rejeitada pelo SEFAZ: Código 215 - Falha no schema XML.",
  "request_id": "..."
}
```

---

# 5.5. TERMINAL / PDV

| Código | HTTP | Descrição |
|--------|------|------------|
| `PDV_4001` | 400 | Terminal não autorizado |
| `PDV_4002` | 400 | Terminal não vinculado à filial |
| `PDV_5001` | 500 | Erro inesperado do terminal |

---

# 5.6. INTERNAL (Erros inesperados)

| Código | HTTP | Descrição |
|--------|------|------------|
| `INTERNAL_5000` | 500 | Erro inesperado |
| `INTERNAL_5001` | 500 | Exceção não tratada |
| `INTERNAL_5002` | 500 | Falha catastrófica |

**Regra:**
Nunca vazar stack trace para o PDV.
Stack trace vai apenas para:

- Logs (nível ERROR)
- Sentry (obrigatório)

---

# 6. Mapeamento SEFAZ → API

Exemplos:

```
[Sefaz] Autorizado uso da NF-e (100)
→ HTTP 200 + registro normal + auditoria

[Sefaz] Rejeição 215 - Falha schema XML
→ HTTP 409 + FISCAL_4007

[Sefaz] Rejeição 999 - Erro não catalogado
→ HTTP 409 + FISCAL_4004

[Sefaz] Timeout ou falha de comunicação
→ HTTP 502 + FISCAL_5005
```

Todos carregam:

```
request_id
tenant_id
filial_id
terminal_id
```

---

# 7. Mapeamento de Exceções Internas → API

| Exceção | Retorno API |
|--------|--------------|
| `DoesNotExist` | VALID_4000 / 404 |
| `IntegrityError` | VALID_4000 / 409 |
| `ValueError` | VALID_4000 |
| `PermissionDenied` | AUTH_4002 |
| `ValidationError` | VALID_4000 |
| `TimeoutError` | FISCAL_5005 |
| `Exception` | INTERNAL_5000 |

---

# 8. Exemplo Completo de Resposta

```json
{
  "error": "FISCAL_4007",
  "message": "Rejeitada pelo SEFAZ: Código 215 - Falha no schema.",
  "details": {
    "codigo_sefaz": "215",
    "motivo": "Falha no schema XML"
  },
  "request_id": "0899c36c-40be-48fa-bb17-dddc7f86d2fd"
}
```

---

# 9. Log + API + Auditoria (triangulação)

Para cada erro fiscal:

- **API** responde erro padronizado
- **Logs** registram evento conforme logbook
- **Auditoria** registra quando apropriado

Fluxo:

```
NfceEmissaoService
    → client SEFAZ
        → sucesso/rejeição/erro
            → API retorna FISCAL_XXXX
            → Log fiscal (nfce_emissao_*)
            → Auditoria (conforme regra)
```

---

# 10. Conclusão

Este documento garante:

- Qualidade dos retornos
- Previsibilidade para o app POS
- Padronização total entre módulos
- Redução de bugs em QA
- Auditoria e compliance

Qualquer novo módulo deve seguir este padrão.
