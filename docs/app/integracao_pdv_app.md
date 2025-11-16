# Integração do App PDV com o Backend — GetStart PDV

## 1. Objetivo

Este documento define como o **aplicativo do PDV** (desktop/mobile) integra com o **backend do GetStart PDV**, cobrindo:

- Autenticação (JWT Bearer)
- Cabeçalhos obrigatórios (tenant, terminal, filial)
- Padrões de requisição e resposta
- Tratamento de erros (usando `guia_erros_excecoes.md`)
- Fluxos críticos: venda, pré-emissão, emissão NFC-e, cancelamento, inutilização
- Boas práticas de uso da API em contexto POS (sem navegador)

> Importante: o PDV **não é um sistema web/browser**.  
> Não existe XSS, cookies ou sessão de navegador.  
> Toda integração é feita via **HTTP + JSON + JWT**.

---

## 2. Autenticação

### 2.1. Login

O app PDV autentica o usuário via endpoint de login:

```http
POST /api/auth/login/
Content-Type: application/json
```

Body (exemplo):

```json
{
  "usuario": "operador1",
  "senha": "senha_secreta",
  "tenant_id": "12345678000199"
}
```

Resposta (exemplo):

```json
{
  "access_token": "<jwt_access>",
  "refresh_token": "<jwt_refresh>",
  "user": {
    "id": 1,
    "nome": "Operador 1",
    "perfis": ["OPERADOR"],
    "filiais": [...]
  }
}
```

### 2.2. Uso do JWT

Todas as requisições autenticadas devem conter:

```http
Authorization: Bearer <access_token>
X-Tenant-ID: <cnpj_raiz>
```

- O app é responsável por armazenar o `access_token`/`refresh_token`.
- Em caso de expiração, o app chama o endpoint de **refresh**.

---

## 3. Cabeçalhos Obrigatórios

Para **toda requisição** do PDV ao backend:

- `Authorization: Bearer <access_token>`
- `X-Tenant-ID: <cnpj_raiz>`  (ex.: `12345678000199`)

Para operações fiscais (NFC-e), recomenda-se também enviar:

- `X-Filial-Id: <uuid_filial>`
- `X-Terminal-Id: <uuid_terminal>`

Esses cabeçalhos ajudam:

- Multi-tenant (resolver schema)
- Controle de acesso por filial
- Auditoria e logs

---

## 4. Padrão de Respostas (Sucesso vs Erro)

### 4.1. Sucesso (2xx)

Respostas de sucesso retornam:

- `status 200`, `201`, `204`, etc.
- Corpo JSON com dados da operação.

Exemplo emissão NFC-e:

```json
{
  "status": "AUTORIZADA",
  "chave": "3519...",
  "protocolo": "123456",
  "numero": 123,
  "serie": 1,
  "ambiente": "homolog",
  "dhEmi": "2025-01-01T12:00:00Z"
}
```

### 4.2. Erros (4xx/5xx)

Todos erros seguem:

```json
{
  "error": "<CODIGO_DO_ERRO>",
  "message": "<mensagem_legivel>",
  "details": { ... },    // opcional
  "request_id": "<uuid>"
}
```

Exemplos típicos:

- `AUTH_4001` → credenciais inválidas  
- `TENANT_4001` → header `X-Tenant-ID` ausente  
- `FISCAL_4007` → problema de dados fiscais (XML, CFOP, NCM etc.)  
- `FISCAL_5001` → erro de comunicação com SEFAZ  

O app deve:

- Exibir `message` ao operador (quando apropriado).
- Usar `error` para mapear tratamento interno (ex.: alerta, bloqueio, sugestão de contatar suporte).
- Logar `request_id` para suporte.

---

## 5. Fluxo de Venda e Emissão NFC-e

### 5.1. Pré-emissão

O app envia os dados da venda para o backend, que cria uma **pré-emissão**:

```http
POST /api/fiscal/nfce/pre_emissao/
```

Exemplo de body:

```json
{
  "filial_id": "...",
  "terminal_id": "...",
  "itens": [
    {
      "produto_id": 1,
      "quantidade": 2,
      "valor_unitario": 50.00,
      "desconto": 0.00
    }
  ],
  "pagamentos": [
    {
      "tipo": "DINHEIRO",
      "valor": 100.00
    }
  ],
  "cliente": {
    "cpf": "12345678909"
  }
}
```

Resposta (pré-emissão criada):

```json
{
  "request_id": "e2557ca7-031a-4b94-afc0-434a2c6d929c",
  "pre_emissao_id": "uuid",
  "status": "PENDENTE"
}
```

### 5.2. Emissão NFC-e

O app então chama:

```http
POST /api/fiscal/nfce/emitir/
```

Body:

```json
{
  "request_id": "e2557ca7-031a-4b94-afc0-434a2c6d929c"
}
```

Resposta de sucesso:

```json
{
  "status": "AUTORIZADA",
  "chave": "3519...",
  "protocolo": "123456",
  "numero": 123,
  "serie": 1,
  "dhEmi": "2025-01-01T12:00:00Z",
  "ambiente": "homolog"
}
```

> **Regra importante:**  
> `request_id` garante **idempotência**.  
> Se o app reenviar a mesma requisição, o backend não deve emitir outra NFC-e para o mesmo `request_id`.

---

## 6. Cancelamento NFC-e (via App)

### 6.1. Endpoint

```http
POST /api/fiscal/nfce/cancelar/
```

Body:

```json
{
  "filial_id": "...",
  "terminal_id": "...",
  "chave": "3519...<44>",
  "motivo": "Cliente desistiu da compra."
}
```

Resposta de sucesso:

```json
{
  "status": "CANCELADA",
  "chave": "3519...",
  "protocolo": "1234567890",
  "data_evento": "2025-01-01T12:34:56Z"
}
```

Em caso de rejeição SEFAZ:

```json
{
  "error": "FISCAL_400x",
  "message": "Rejeitada pelo SEFAZ: Código 217 - NFC-e não encontrada.",
  "request_id": "..."
}
```

O app deve:

- Exibir claramente se o cancelamento foi aceito ou não.
- Não tentar re-cancelar em loop sem interação do operador.

---

## 7. Inutilização de Numeração (via App Admin)

Usado raramente, em telas mais administrativas.

```http
POST /api/fiscal/nfce/inutilizar/
```

Body:

```json
{
  "filial_id": "...",
  "serie": 1,
  "numero_inicial": 151,
  "numero_final": 160,
  "motivo": "Falha técnica no terminal."
}
```

Resposta:

```json
{
  "status": "INUTILIZADA",
  "protocolo": "123456",
  "serie": 1,
  "numero_inicial": 151,
  "numero_final": 160
}
```

---

## 8. Contingência (EPEC / Offline)

Conforme `contingencia_nfce.md`, o fluxo será:

- App tenta emitir normalmente.  
- Se recebe erro `FISCAL_500x` (SEFAZ indisponível / timeout etc.), pode chamar:

```http
POST /api/fiscal/nfce/contingencia/opcoes/
```

Resposta (exemplo):

```json
{
  "modo_contingencia": "epec",
  "motivo": "SEFAZ indisponível",
  "detalhes": {
    "uf": "SP"
  }
}
```

O app então:

- Adequa interface (indicar que está em contingência).  
- Segue o fluxo definido para EPEC (fase futura).

---

## 9. Sincronização e Operação Offline do App

O backend não conhece diretamente se o app está offline ou não, mas:

- O app pode operar com **fila local** (não é escopo deste doc técnico).  
- Quando voltar a ter conexão, sincroniza com o backend:

Exemplo:

```http
POST /api/pdv/sincronizar_vendas/
```

E o backend:

- Valida vendas pendentes.
- Cria pré-emissões.
- Emite NFC-e (normal ou em contingência).
- Retorna status por venda.

---

## 10. Boas Práticas para o App

1. **Sempre enviar `X-Tenant-ID`**.  
2. **Nunca armazenar senha em texto puro**.  
3. **Rotacionar tokens** usando refresh token de forma segura.  
4. **Não tentar emitir diretamente para SEFAZ** — tudo deve passar pelo backend.  
5. **Usar o `request_id`** fornecido pelo backend para idempotência.  
6. **Logar `request_id` + `error`** localmente quando ocorrer erro.  
7. **Respeitar mensagens fiscais** — não maquiar mensagens críticas de erro fiscal.  
8. **Testar com ambientes mock/homolog antes de produção**.

---

## 11. Integração com Logs e Auditoria

O app **não vê** diretamente os logs/auditoria, mas:

- Toda operação relevante recebe um `request_id`.
- Esse `request_id` é usado:
  - Em logs (`nfce_emissao_*`, `nfce_cancelamento_*`, `nfce_inutilizacao_*`).  
  - Na tabela `NfceAuditoria`.

Em caso de suporte:

- O suporte pedirá o `request_id` exibido no erro.  
- Com isso, encontra o evento completo no backend.

---

## 12. Conclusão

Este documento define:

- Como o **app PDV** conversa com o backend (autenticação, headers, fluxo).  
- Como consumir os endpoints fiscais (pré-emissão, emissão, cancelamento, inutilização).  
- Como tratar erros (segundo o `guia_erros_excecoes.md`).  
- Como alinhar o comportamento do app com as regras fiscais e operacionais do GetStart PDV.

Ele deve ser seguido por qualquer equipe que for implementar o app POS (desktop/mobile) que converse com este backend.
