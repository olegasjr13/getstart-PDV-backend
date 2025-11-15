
---

## 2️⃣ `docs/arquitetura/sequencias_arquitetura.md`

```markdown
# Sequências Arquiteturais — GetStart PDV

Este documento apresenta **diagramas de sequência de alto nível**, conectando os componentes definidos em `componentes.md` com os fluxos principais de negócio.

---

## 1. Login e Contexto de Filial/Terminal

```mermaid
sequenceDiagram
  participant PDV as App PDV
  participant NGINX as Nginx Proxy
  participant BE as Backend API
  participant DB as DB Multi-tenant

  PDV->>NGINX: POST /api/v1/auth/login (username, password, terminal_id)
  NGINX->>BE: repassa requisição
  BE->>DB: autentica usuário (public schema)
  BE->>DB: verifica vínculo user↔filial↔terminal (schema tenant)
  DB-->>BE: dados do usuário, perfil, filial, terminal
  BE-->>PDV: 200 (access, refresh, contexto de trabalho)
