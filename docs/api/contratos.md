# Contratos de API — GetStart PDV Backend

## 1. Objetivo

Definir as **regras contratuais padrão** da API do GetStart PDV:

- Formato de requests/responses.
- Autenticação.
- Headers obrigatórios.
- Convenções de erro.
- Versionamento.
- Idempotência.

Este documento complementa o `openapi.yaml` e é referência para **Frontend**, **Mobile/PDV** e **integradores**.

---

## 2. Base URL e versionamento

### 2.1 URL base

Ambiente típico:

- `https://api.getstartpdv.com/api/v1/`

Estrutura:

- `/api/v1/<recurso>/<ação>`

### 2.2 Versionamento

- A versão da API faz parte da URL:
  - `v1` é a versão estável atual.
- Mudanças **breaking** deverão:
  - Ser expostas como `/api/v2/...`, mantendo `/api/v1` por período de convivência.

---

## 3. Autenticação

### 3.1 JWT (Bearer Token)

- Autenticação via **JWT** emitido pelo endpoint:
  - `POST /auth/login`
- O token é enviado via header:
  - `Authorization: Bearer <access_token>`

### 3.2 Conteúdo mínimo do token

Claims relevantes (padrão v1):

- `sub` — `user_id`.
- `perfil` — perfil do usuário (`OPERADOR`, `SUPERVISOR`, `GERENTE`, `ADMIN`).
- `filial_id` — filial atual da sessão.
- `terminal_id` — terminal ativo na sessão (quando aplicável).
- `exp` — expiração.

### 3.3 Renovação de token

- Endpoint:
  - `POST /auth/refresh`
- Body:
  - `{"refresh": "<refresh_token>"}`

---

## 4. Multi-Tenancy

### 4.1 Header `X-Tenant-ID`

Seleção do tenant (schema) via header obrigatório:

```http
X-Tenant-ID: <cnpj_raiz>
Valor = CNPJ raiz do cliente (somente números, ex.: 12345678000199).

Endpoints de contexto público (provisionamento, saúde, etc.) podem omitir esse header, quando documentado.

4.2 Regras

Requests sem X-Tenant-ID em endpoints de tenant:

Erro TENANT_1001.

O backend não deve inferir tenant por host na versão atual, apenas por header.

5. Formato de dados
5.1 JSON

Requests:

Content-Type: application/json

Responses:

Content-Type: application/json (exceto endpoints específicos, ex.: download de DANFE PDF).

5.2 Datas e horários

Formato ISO 8601 com timezone (preferencialmente UTC):

2025-07-01T12:34:56Z

5.3 Valores monetários

Número decimal com duas casas:

Ex.: 10.00, 123.45.

Internamente: DECIMAL(15,2).

5.4 Identificadores

UUID canonical:

xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

6. Convenções de resposta
6.1 Sucesso (2xx)

Para recurso único:

{
  "data": {
    "id": "7b0f8c95-4ae4-4e35-9c18-0d7cfdaf0001",
    "campo": "valor"
  }
}


Para lista:

{
  "data": [
    { "id": "...", "campo": "..." },
    { "id": "...", "campo": "..." }
  ],
  "meta": {
    "page": 1,
    "page_size": 50,
    "total": 137
  }
}

6.2 Erro (4xx/5xx)
{
  "error": {
    "code": "FISCAL_4005",
    "message": "Certificado A1 expirado para a filial.",
    "details": {
      "filial_id": "f5bb9e8e-5c3e-4b09-a1a3-000000000001",
      "a1_expires_at": "2025-06-30T23:59:59Z"
    }
  }
}


code: código interno (catalogado em erros_api.md / erros_fiscais.md).

message: mensagem clara em PT-BR.

details: dados técnicos adicionais (sem PII sensível).

7. Paginação, filtro e ordenação
7.1 Paginação

Parâmetros:

page (1-based).

page_size.

Resposta:

{
  "data": [ ... ],
  "meta": {
    "page": 1,
    "page_size": 50,
    "total": 137
  }
}

7.2 Filtros

?search=<termo>

Filtros específicos:

?ativo=true

?filial_id=<uuid>

etc. (documentado por endpoint em openapi.yaml).

7.3 Ordenação

?ordering=campo

?ordering=-campo (descendente)

8. Idempotência
8.1 request_id

Aplica para:

POST /fiscal/nfce/reservar-numero

POST /fiscal/nfce/pre-emissao

POST /fiscal/nfce/emissao

Regra:

Mesmo request_id → mesmo resultado lógico.

O backend não deve criar nova reserva/pre-emissão/emissão com request_id já usado.

8.2 local_tx_uuid (offline)

Para:

POST /sync/outbox

Regra:

Mesmo local_tx_uuid → evento tratado como já processado.

Não gera efeitos colaterais duplicados.

9. Versionamento de contratos

Alterações não-breaking:

Novos campos opcionais.

Novos endpoints.

Novos valores de enum aceitos.

Alterações breaking:

Mudança de tipo.

Remoção de campos.

Mudança de semântica de campo obrigatório.

Para alterações breaking:

Expor nova versão (/api/v2/...) ou

Introduzir recursos com novos nomes, mantendo versão antiga em modo deprecated.

10. Segurança

Sempre via HTTPS.

Nunca expor em responses:

Senhas.

PINS.

Dados completos de cartão.

Chaves privadas ou conteúdo do A1.

Erros 5xx devem ser genéricos para o cliente, com detalhes completos apenas em logs internos.
