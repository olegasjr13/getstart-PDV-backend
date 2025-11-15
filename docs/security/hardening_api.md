
---

## `security/hardening_api.md`

```markdown
# Hardening de API — GetStart PDV

## 1. Objetivo

Definir as práticas de segurança específicas da **API HTTP** do GetStart PDV:

- Autenticação e autorização.
- Proteção contra abuso (rate limiting, brute force).
- CORS, CSRF e origem confiável.
- Validação de entrada e saída.
- Boas práticas de erros e respostas.

---

## 2. Autenticação

### 2.1 Padrão recomendado

- Auth baseada em **JWT**:
  - **Access token**:
    - TTL curto (ex.: 5–15 minutos).
  - **Refresh token**:
    - TTL maior (ex.: 7–30 dias).
- Envio em:
  - Header: `Authorization: Bearer <access_token>`  
    **ou**
  - Cookie `HttpOnly` (arquitetura já prevista no projeto maior).

### 2.2 Boas práticas

- Algoritmo seguro (ex.: HS256 com chave forte, ou RS256 com par de chaves).
- Rotacionar chaves (key rotation) se possível.
- Incluir em claims:
  - `sub` = user_id
  - `perfil` = role (OPERADOR, SUPERVISOR, etc.)
  - `tenant_id`
  - `filial_id` (quando sessão travada a uma filial)
- Em caso de refresh:
  - Verificar se usuário ainda está ativo.
  - Verificar se tenant e filial ainda estão ativos.

### 2.3 Revogação de tokens

- Em incidentes (comprometimento de conta ou key):
  - Invalidar refresh tokens (ex.: tabela/blacklist com `jti`).
  - Forçar login novamente.
- Access tokens curtos minimizam impacto.

---

## 3. Autorização (RBAC)

- Perfis de usuário:
  - `OPERADOR`: operações de venda.
  - `SUPERVISOR`: cancelamentos, reimpressões, etc.
  - `GERENTE`: cadastros, configurações de loja.
  - `ADMIN`: nível máximo (interno à plataforma).
- Cada endpoint deve declarar **claramente**:
  - Quais perfis podem acessá-lo.
- Implementar camada de autorização:
  - Decoradores ou permissões (ex.: DRF `permissions`).

---

## 4. CORS

### 4.1 Configuração

- Em produção:
  - Lista **explícita** de origens permitidas:
    - `https://app.getstartpdv.com`
    - `https://painel.getstartpdv.com`
  - Nunca usar `CORS_ALLOW_ALL_ORIGINS = True` em produção.
- Em dev:
  - Pode permitir `localhost` com portas específicas.

### 4.2 Headers

- Permitir apenas o necessário:
  - `Authorization`
  - `Content-Type`
  - `X-Tenant-ID`
  - Eventuais headers customizados necessários.

---

## 5. Proteção contra brute force e abuso

### 5.1 Login

- Limitar tentativas de login por:
  - IP
  - Usuário
  - Tenant
- Ferramentas:
  - Rate-limit por endpoint com Redis ou middleware específico.
- Exemplo:
  - Máx. 5 tentativas em 5 minutos → após isso, retornar erro genérico (sem dizer se usuário existe).

### 5.2 Endpoints críticos

Aplicar rate limit reforçado em:

- `/auth/login`
- `/auth/refresh`
- `/fiscal/nfce/*`
- `/sync/outbox` (prevenir bombardeio descontrolado).

### 5.3 Tamanho de payload

- Limitar `Content-Length` máximo:
  - Ex.: 2MB (ajustar conforme necessidade, principalmente em sync/outbox).
- Rejeitar payloads acima do limite com HTTP 413.

---

## 6. Validação de entrada

### 6.1 Princípios

- Nunca confiar em dados do cliente (PDV/Frontend).
- Validar:
  - Tipos (string, int, decimal).
  - Faixas (número de itens, valor máximo).
  - Comprimento (número de caracteres).
  - Formatos (CPF, CNPJ, e-mail, etc.).

### 6.2 Exemplos práticos

- No fiscal:
  - Garantir que `serie` é inteiro e > 0.
  - `numero` jamais vem do cliente (sempre gerado no backend).
  - `request_id` deve ser UUID válido.
- Em sync:
  - Validar `event_type` contra lista de tipos suportados.
  - Validar estrutura de `payload` por tipo.

---

## 7. Saída e mensagens de erro

### 7.1 Não vazar detalhes internos

- Em erros 5xx:
  - Mensagem genérica para o cliente:  
    `Ocorreu um erro interno. Tente novamente mais tarde.`
  - Detalhes completos **apenas em logs**.
- Em erros 4xx:
  - Mensagem clara e amigável, mas sem:
    - Expor estruturas internas de banco.
    - Mostrar stacktrace.

### 7.2 Uso consistente dos códigos de erro

- Sempre retornar `error.code`:
  - `AUTH_1000`, `FISCAL_4005`, etc.
- Catálogo de códigos:
  - `api/erros_api.md`
  - `fiscal/erros_fiscais.md`

---

## 8. CSRF

### 8.1 Quando relevante

- Se tokens JWT são enviados via **cookie** e chamadas são feitas como **browser normal**, há risco de CSRF.
- Se tokens são enviados via header `Authorization` e o frontend controla isso com JS, o risco é menor (mas ainda é preciso avaliar).

### 8.2 Medidas

- Usar `CSRF` do Django para endpoints de sessão/cookie.
- Para APIs puras com JWT em header:
  - Bloquear cookies de sessão em APIs públicas.
  - Garantir CORS estrito + não usar `withCredentials` sem necessidade.

---

## 9. Segurança de arquivos e uploads (se/ quando existirem)

- Limitar tipo de arquivo (MIME + extensão).
- Configurar storage separado (ex.: S3, GCS, volume específico).
- Não permitir execução de arquivos uploadados.
- Verificar tamanho máximo.

---

## 10. Logging, auditoria e correlação

- Para cada requisição:
  - Incluir `request_id` (ex.: header `X-Request-ID`, ou gerado no backend).
- Para eventos fiscais:
  - Sempre logar `tenant_id`, `filial_id`, `terminal_id`, `request_id`, `chave` (quando existir).

---

## 11. Checklists para API segura

- [ ] CORS limitado a origens confiáveis.
- [ ] JWT com TTL adequado e refresh implementado.
- [ ] Rate limit em login e endpoints críticos.
- [ ] Validação forte de payload em todos endpoints.
- [ ] Estrutura de erro padronizada (`error.code`, `error.message`).
- [ ] Nenhum stacktrace ou info sensível vaza em resposta.
- [ ] Logs com contexto, mas sem segredos.

---
