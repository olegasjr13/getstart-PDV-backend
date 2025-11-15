# Guia Oficial de Erros e Exceções — GetStart PDV (Versão Enterprise)
Versão: 1.0
Responsável: Arquitetura Backend

---

# 1. Objetivo
Este documento define **toda a padronização oficial** de erros, exceções, códigos fiscais, mensagens e estrutura de respostas do backend GetStart PDV.

Ele foi criado baseado diretamente no comportamento real do backend, incluindo:
- Exceptions personalizadas do projeto
- Tratamento de erros fiscais
- Tratamento de erros de autenticação
- Tratamento de erros multi-tenant
- Estrutura de erro adotada nas views e services
- Testes fiscais existentes no projeto

O objetivo é garantir:
- Padronização absoluta
- Previsibilidade do comportamento da API
- Transparência para frontend (PDV móvel)
- Rastreabilidade para auditoria fiscal
- Coerência para QA automatizar cenários

---

# 2. Estrutura Padrão de Erro na API

Toda resposta de erro da API deve seguir este formato:

```json
{
  "error": {
    "code": "FISCAL_4003",
    "message": "Divergência de totais.",
    "details": {... opcional ...}
  }
}
```

### 2.1 Campos obrigatórios

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| error.code | string | ✔️ | Identificador único do erro |
| error.message | string | ✔️ | Mensagem legível |
| error.details | object | opcional | Campos adicionais |

### 2.2 Regras Gerais

- Nunca retornar traceback para o cliente.
- Nunca retornar exceções nativas brutas.
- Todo erro deve ter **code + message**.
- `code` deve ter um prefixo identificando o módulo.

Ex:
- `AUTH_1001`
- `FISCAL_4003`
- `TENANT_2002`

---

# 3. Categorias Oficiais de Erros

O projeto possui 4 categorias:

| Categoria | Prefixo | Uso |
|----------|---------|-----|
| Autenticação | AUTH | Login, token, permissões |
| Fiscal | FISCAL | Regras NFC-e |
| Multi-tenant | TENANT | Schema, domínio, contexto |
| Genérico | SYS | Erros inesperados |

---

# 4. Erros de Autenticação (AUTH_1xxx)

Baseados na lógica real do backend:

| Código | Mensagem |
|--------|----------|
| AUTH_1000 | Credenciais inválidas |
| AUTH_1001 | Usuário inativo |
| AUTH_1002 | Tenant não autorizado |
| AUTH_1003 | Token expirado |
| AUTH_1004 | Refresh token inválido |

Formato real:

```json
{
  "error": {
    "code": "AUTH_1000",
    "message": "Credenciais inválidas."
  }
}
```

---

# 5. Erros Fiscais (FISCAL_4xxx)

Baseados diretamente nos services do módulo fiscal e nos testes do projeto.

| Código | Mensagem |
|--------|----------|
| FISCAL_4001 | Terminal inválido |
| FISCAL_4002 | Solicitação duplicada (request_id) |
| FISCAL_4003 | Divergência de totais |
| FISCAL_4004 | Item inválido |
| FISCAL_4005 | Pagamento inválido |
| FISCAL_4006 | Pré-emissão não encontrada |
| FISCAL_4007 | Reserva não encontrada |
| FISCAL_4008 | Terminal inativo |
| FISCAL_4010 | Tentativa de emitir sem pré-emissão |
| FISCAL_4015 | Pagamentos não correspondem ao valor total (planejado) |
| FISCAL_4020 | Cancelamento bloqueado sem estorno (planejado) |

### Exemplo real:

```json
{
  "error": {
    "code": "FISCAL_4003",
    "message": "Divergência de totais.",
    "details": {
      "valor_itens": 100,
      "valor_pagamentos": 80
    }
  }
}
```

---

# 6. Erros Multi-Tenant (TENANT_2xxx)

Relativos ao schema e domínio.

| Código | Mensagem |
|--------|----------|
| TENANT_2001 | Tenant não encontrado |
| TENANT_2002 | Schema inválido |
| TENANT_2003 | Domínio não autorizado |
| TENANT_2004 | Tenant desativado |

### Exemplo:

```json
{
  "error": {
    "code": "TENANT_2003",
    "message": "Domínio não autorizado."
  }
}
```

---

# 7. Erros Genéricos (SYS_5xxx)

Sempre retornam **500**, sem expor detalhes sensíveis.

| Código | Mensagem |
|--------|----------|
| SYS_5000 | Erro interno inesperado |
| SYS_5001 | Falha ao processar requisição |
| SYS_5002 | Serviço indisponível |

### Exemplo:

```json
{
  "error": {
    "code": "SYS_5000",
    "message": "Erro interno inesperado."
  }
}
```

---

# 8. Padronização no Código (Backend)

### 8.1 Estrutura recomendada de exceções

```python
class FiscalException(APIException):
    status_code = 400
    code = "FISCAL_4000"
    default_detail = "Erro fiscal genérico."
```

### 8.2 Lançando exceções em services

```python
raise FiscalException(
    detail={"code": "FISCAL_4003", "message": "Divergência de totais."}
)
```

### 8.3 Nas views

Nunca tratar erro manualmente, deixar DRF converter a exceção.

---

# 9. Padrões Específicos para Logs em Erros

Todo erro deve resultar em log com:

- event = `<module>_erro`
- level = ERROR
- code
- tenant
- request_id

Ex:

```json
{
  "event": "fiscal_erro",
  "code": "FISCAL_4003",
  "tenant": "12345678000199",
  "request_id": "abc-123"
}
```

---

# 10. Regras para QA criar testes de erro

### Testes obrigatórios:
- Credenciais inválidas
- Terminal inválido
- Pré-emissão inexistente
- Totais divergentes
- Request_id repetido
- Token expirado
- Tenant errado

Todos os testes devem verificar **error.code**.

Exemplo:

```python
assert resp.json()["error"]["code"] == "FISCAL_4003"
```

---

# 11. Conclusão

Este documento estabelece o padrão único de erros e exceções do backend GetStart PDV.
Toda nova API deve obrigatoriamente seguir este guia, com códigos consistentes, mensagens claras e logs correlacionáveis.
