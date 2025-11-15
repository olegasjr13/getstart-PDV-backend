
---

## 2️⃣ `api/dicionario_endpoints.md` — Versão Ajustada (mais fechada e limpa)

Aqui está uma versão **consolidada**, coerente com o que foi descrito em contratos, fiscal, sync, etc.

```markdown
# Dicionário de Endpoints — GetStart PDV (v1)

Este documento descreve **rota a rota** os principais endpoints do backend GetStart PDV:

- Objetivo funcional
- Regras de negócio
- Estrutura de request/response
- Erros típicos
- Relação com dados e fluxos

> Este documento complementa:
> - `api/contratos.md` (padrões gerais)
> - `api/erros_api.md` (catálogo de erros)
> - `fiscal/regras_fiscais.md` (regras NFC-e)
> - `fiscal/erros_fiscais.md` (erros FISCAL_*)

---

## 1. Autenticação

### 1.1 `POST /auth/login`

**Objetivo**
Autenticar usuário e retornar `access_token`, `refresh_token` e dados básicos do usuário.

**Regras principais**

- Usuário deve:
  - Pertencer ao `tenant` (ver `X-Tenant-ID` ou body).
  - Estar `ativo`.
- Senha verificada via hash seguro.
- Perfis (`perfil`) usados para autorização posterior (`OPERADOR`, `SUPERVISOR`, etc.).
- Em caso de falha:
  - Incremento de contador de tentativas (mitigação brute-force).

**Headers**

- `X-Tenant-ID: <cnpj_raiz>` (obrigatório para tenants).
- `Content-Type: application/json`

**Request body**

```json
{
  "email": "operador@loja.com",
  "senha": "123456"
}
Em algumas arquiteturas, tenant_id pode vir no body; aqui recomendamos uso do header.

Response 200

{
  "access_token": "<jwt>",
  "refresh_token": "<jwt>",
  "user": {
    "id": 12,
    "nome": "Operador 01",
    "perfil": "OPERADOR",
    "tenant_id": "12345678000199",
    "filiais": [
      {
        "id": "a7efae65-640e-49dd-bef2-9ced32fa8b84",
        "nome": "Loja Centro"
      }
    ]
  }
}


Erros típicos

401 AUTH_1000 — Credenciais inválidas.

403 AUTH_1001 — Usuário inativo ou sem permissão.

400 TENANT_1001 — Header X-Tenant-ID ausente.

404 TENANT_1002 — Tenant não encontrado.

1.2 POST /auth/refresh

Objetivo
Renovar access_token a partir de refresh_token.

Request

{
  "refresh_token": "<jwt_refresh>"
}


Response 200

{
  "access_token": "<jwt_novo>"
}


Erros típicos

401 AUTH_1002 — Refresh inválido ou expirado.

2. Fiscal — NFC-e

Fluxo completo descrito em: fiscal/regras_fiscais.md e fluxos/bpmn_negocio.md.

2.1 POST /fiscal/nfce/reserva

Objetivo
Reservar número para NFC-e, garantindo:

Sequencialidade por (tenant, filial, terminal, serie).

Idempotência por request_id.

Regras

Deve ser sempre o primeiro passo da emissão.

request_id deve ser UUID gerado pelo PDV e reutilizado nas próximas etapas.

Se request_id já usado:

Backend retorna mesma reserva (não cria nova).

Request

{
  "request_id": "e2557ca7-031a-4b94-afc0-434a2c6d929c",
  "filial_id": "a7efae65-640e-49dd-bef2-9ced32fa8b84",
  "terminal_id": "5f2b39ed-90d0-4800-be75-f1aced155c21",
  "serie": 1
}


Response 201 (created)

{
  "data": {
    "id_reserva": "41ab0e2e-9cc4-4f8e-9b5f-3bfbe2a7d001",
    "numero": 1028,
    "serie": 1,
    "status": "RESERVADO"
  }
}


Campos críticos

numero é sempre calculado no backend (nunca vem do cliente).

status inicial: RESERVADO.

Erros típicos

404 FISCAL_4008 — Terminal não encontrado ou não vinculado à Filial.

422 FISCAL_4001 — Filial sem certificado A1.

422 FISCAL_4005 — Certificado A1 expirado.

2.2 POST /fiscal/nfce/pre-emissao

Objetivo
Registrar os dados completos da venda antes da emissão fiscal.

Regras

Exige que exista reserva válida para o request_id.

Deve conter:

Itens da venda.

Pagamentos.

Totais.

Request (exemplo simplificado)

{
  "request_id": "e2557ca7-031a-4b94-afc0-434a2c6d929c",
  "cliente": {
    "cpf": "00000000000",
    "nome": "CONSUMIDOR"
  },
  "itens": [
    {
      "codigo": "123",
      "descricao": "Produto X",
      "quantidade": 2,
      "unidade": "UN",
      "valor_unitario": 10.00,
      "valor_total": 20.00
    }
  ],
  "pagamentos": [
    {
      "tipo": "DINHEIRO",
      "valor": 20.00
    }
  ],
  "total_nfce": 20.00,
  "descontos": 0.00,
  "acrescimos": 0.00
}


Response 201

{
  "data": {
    "id_pre_emissao": "9f03...",
    "request_id": "e2557ca7-031a-4b94-afc0-434a2c6d929c",
    "status": "PRE_EMITIDA"
  }
}


Erros típicos

404 FISCAL_4010 — Reserva não encontrada para request_id.

422 FISCAL_4030 — Totais inconsistentes (itens x pagamentos x total).

2.3 POST /fiscal/nfce/emissao

Objetivo
Emitir a NFC-e, usando dados da pré-emissão e retornando:

chave

protocolo

XML (mock ou real)

Dados para DANFE

Regras

Exige request_id previamente usado em:

/reserva

/pre-emissao

Em modo mock:

Gera protocolo simulado.

Em modo real:

Envia XML assinado para SEFAZ.

Request

{
  "request_id": "e2557ca7-031a-4b94-afc0-434a2c6d929c"
}


Response 201

{
  "data": {
    "numero": 1028,
    "serie": 1,
    "chave": "35191112345678000199550010000010281000010280",
    "protocolo": "135190000000000",
    "status": "AUTORIZADA",
    "xml": "<NFe>...</NFe>",
    "danfe_base64": null
  }
}


danfe_base64 pode ser preenchido caso o backend gere DANFE em PDF/PNG. Ver fiscal/guia_danfe_nfce.md.

Erros típicos

404 FISCAL_4010 — Pré-emissão não encontrada para request_id.

422 FISCAL_4001 / 4005 — Problemas com certificado A1.

Erros de rejeição SEFAZ (na fase real).

2.4 POST /fiscal/nfce/cancelar

Objetivo
Solicitar cancelamento de uma NFC-e.

Regras

NFC-e deve estar em status AUTORIZADA.

É obrigatório que o estorno financeiro (caixa/pagamento) tenha sido realizado antes:

Senão → FISCAL_4020.

Request

{
  "chave": "35191112345678000199550010000010281000010280",
  "justificativa": "Cliente desistiu da compra."
}


Response 200

{
  "data": {
    "chave": "3519...",
    "status": "CANCELADA",
    "protocolo_cancelamento": "135190000000001"
  }
}


Erros típicos

404 — NFC-e não encontrada.

422 FISCAL_4020 — Estorno financeiro obrigatório antes de cancelar.

3. Sync/Outbox
3.1 POST /sync/outbox

Objetivo
Receber eventos gerados offline pelo PDV e processá-los de forma idempotente.

Regras

Cada evento possui local_tx_uuid.

Se local_tx_uuid já foi processado:

Evento é ignorado (marcado como duplicado, mas não gera erro 500).

Tipos de evento (exemplo):

VENDA_FINALIZADA

CANCELAMENTO

MOVIMENTO_CAIXA

Request

{
  "events": [
    {
      "local_tx_uuid": "8f1b266c-15d6-4c6d-9dc1-77a3f8a8c001",
      "event_type": "VENDA_FINALIZADA",
      "payload": {
        "request_id": "e2557...",
        "dados_venda": { "...": "..." }
      },
      "timestamp": "2025-01-01T12:00:00Z"
    }
  ]
}


Response 207 (Multi-Status sugerido) ou 200 com lista de resultados

{
  "results": [
    {
      "local_tx_uuid": "8f1b266c-15d6-4c6d-9dc1-77a3f8a8c001",
      "status": "success",
      "message": null
    }
  ]
}


Erros típicos

400 SYNC_3001 — Payload inválido.

409 SYNC_3002 — Evento duplicado (pode ser tratado como sucesso idempotente).

422 SYNC_3003 — Tipo de evento não suportado.

4. Caixa
4.1 POST /caixa/abrir

Objetivo
Abrir sessão de caixa para um terminal e usuário.

Regras

Não pode existir outra sessão de caixa aberta para:

Mesmo terminal e filial.

Usuário deve ter permissão (perfil adequado).

Request

{
  "filial_id": "a7efae65-640e-49dd-bef2-9ced32fa8b84",
  "terminal_id": "5f2b39ed-90d0-4800-be75-f1aced155c21",
  "saldo_inicial": 100.00
}


Response 201

{
  "data": {
    "sessao_id": "caf1e5d0-...",
    "status": "ABERTO",
    "abertura_em": "2025-01-01T09:00:00Z"
  }
}

4.2 POST /caixa/fechar

Objetivo
Fechar sessão de caixa aberta, consolidando totais.

Regras

Deve existir sessão em ABERTO.

O backend recalcula totais e pode registrar divergência com valor informado pelo operador.

Request

{
  "sessao_id": "caf1e5d0-...",
  "saldo_informado": 520.50
}


Response 200

{
  "data": {
    "sessao_id": "caf1e5d0-...",
    "status": "FECHADO",
    "totais": {
      "vendas": 450.50,
      "estornos": 0.00,
      "suprimentos": 100.00,
      "sangrias": 30.00,
      "saldo_calculado": 520.50,
      "diferenca": 0.00
    }
  }
}

5. Catálogo de Produtos
5.1 GET /catalogo/produtos/sync

Objetivo
Permitir que o PDV sincronize o catálogo de produtos.

Regras

Pode usar:

Versão incremental (versao_catalogo).

Ou sync completo (paginado).

Request (exemplo com query)

GET /catalogo/produtos/sync?versao_atual=10&page=1&page_size=500

Response

{
  "data": [
    {
      "id": "p1",
      "codigo_interno": "123",
      "descricao": "Produto X",
      "unidade": "UN",
      "preco_venda": 10.00,
      "ativo": true,
      "codigos_barras": [
        "7891234567890"
      ]
    }
  ],
  "meta": {
    "page": 1,
    "page_size": 500,
    "total": 1200,
    "versao_catalogo": 12
  }
}


Erros típicos

400 COMMON_9001 — Parametrização inválida.

403 AUTH_1001 — Usuário sem acesso à Filial/Tenant.

6. Observações Gerais

Todos os endpoints seguem:

Padrão de resposta em api/contratos.md.

Catálogo de erros em api/erros_api.md + fiscal/erros_fiscais.md.

Sempre que um novo endpoint for criado:

Atualizar:

openapi.yaml

dicionario_endpoints.md

Se for fiscal, revisar regras_fiscais.md.
