# Componentes da Plataforma — GetStart PDV

Este documento descreve os **componentes principais** da solução GetStart PDV, suas responsabilidades, tecnologias, integrações e pontos de atenção.

---

## 1. Visão Macro da Plataforma

Componentes:

- **Backend (getstart-PDV-backend)**
- **Frontend Web / Painel (getstart-PDV-frontend)**
- **Proxy / Edge (getstart-PDV-nginx)**
- **Infraestrutura (getstart-PDV-infra)**
- **App PDV (Mobile / SmartPOS)** — externo a este repo, mas integrando com a API.

Fluxo básico:

1. PDV / Frontend → NGINX → Backend → Banco multi-tenant.
2. Infra cuida de:
   - Orquestração (Docker Compose / Kubernetes, no futuro).
   - CI/CD.
   - Provisionamento (Terraform).
   - Observabilidade e runbooks.

---

## 2. Backend — `getstart-PDV-backend`

### 2.1 Tecnologias

- **Linguagem:** Python 3.x
- **Framework:** Django + Django REST Framework
- **Multi-tenancy:** django-tenants (schema por tenant)
- **Banco:** PostgreSQL
- **Autenticação:** JWT (SimpleJWT customizado)
- **Padrões:**
  - Domínios organizados por apps (`tenants`, `usuario`, `filial`, `terminal`, `fiscal`, `produto`, `caixa`, `pagamentos`, `sync`).
  - Separação clara de regras fiscais, dados e sync.

### 2.2 Responsabilidades

- Expor API REST documentada em `docs/api/openapi.yaml`.
- Implementar regras fiscais (NFC-e mock, futura emissão real).
- Controlar fluxo de:
  - Login, sessão e contexto (perfil, filial, terminal).
  - Reserva de numeração → Pré-emissão → Emissão → Cancelamento.
  - Caixa (sessão, movimentos, estornos).
  - Catálogo de produtos e códigos de barras.
  - Sync offline (outbox).

### 2.3 Integrações

- Recebe chamadas de:
  - PDV (mobile/smartPOS).
  - Frontend Web.
- Futuras integrações:
  - Gateways TEF/Pix.
  - SEFAZ (para emissão real).
  - Serviços internos (relatórios, BI etc.).

---

## 3. Frontend — `getstart-PDV-frontend`

*(Escopo conceitual aqui, implementação detalhada no próprio repo.)*

### 3.1 Tecnologias típicas previstas

- React / TypeScript ou outro framework moderno de SPA.
- Comunicação via HTTP com a API do backend.
- Armazenamento de token (short-lived) em memória/sessionStorage (sem manipular refresh HttpOnly para segurança).

### 3.2 Responsabilidades

- Painel administrativo:
  - Gestão de filiais, usuários, terminais.
  - Acompanhamento fiscal básico (log de emissões, relatórios).
  - Configuração de catálogo de produtos.
- Telas auxiliares internas (não PDV de loja em si).

### 3.3 Integração com Backend

- Consome:
  - Endpoints públicos/autenticados do `/api/v1`.
- Utiliza:
  - Mesmos contratos definidos em `docs/api/openapi.yaml`.
  - Estratégia de erro descrita em `docs/api/erros_api.md`.

---

## 4. Proxy / Borda — `getstart-PDV-nginx`

### 4.1 Tecnologias

- NGINX (containerizado).
- Configurações separadas por ambiente:
  - `nginx.dev.conf`
  - `nginx.prod.conf`

### 4.2 Responsabilidades

- Terminação HTTPS (TLS).
- Proxy reverso:
  - `/` → frontend (static build).
  - `/api/` → backend Django.
- Camada de segurança HTTP:
  - HSTS.
  - Redirecionamento HTTP → HTTPS.
  - Limitação de headers inseguros.
  - Proteção básica contra host header injection.

### 4.3 Regras de roteamento (conceito)

- Requests para `/api/...`:
  - Encaminhadas ao container/backend.
- Requests para assets estáticos:
  - Servidas diretamente pela instância NGINX do frontend.

---

## 5. Infraestrutura — `getstart-PDV-infra`

### 5.1 Estrutura Geral

- `infra/compose/` — orquestração Docker (dev/homolog/prod).
- `infra/docker/` — imagens base reutilizáveis.
- `infra/env/` — templates de `.env`.
- `infra/terraform/` — IaC (bancos premium, redes, etc.).
- `infra/runbooks/` — procedimentos operacionais.
- `infra/ci/` — scripts e templates de CI/CD.

### 5.2 Responsabilidades

- Provisionar:
  - Banco de dados (incluindo schemas multi-tenant).
  - Serviços de aplicação (backend, frontend, nginx).
- Garantir:
  - Backups.
  - Observabilidade (logs, métricas, alertas).
  - Rollback e recuperação de desastre (DR).

---

## 6. App PDV (Mobile / SmartPOS)

*(Não implementado neste repo, mas fundamental para o desenho do backend.)*

### 6.1 Responsabilidades

- Realizar venda em loja (operador).
- Enviar requisições para:
  - Login.
  - Reserva de número.
  - Pré-emissão.
  - Emissão.
  - Cancelamento.
  - Sync offline (eventos outbox).

### 6.2 Requisitos de Integração

- Sempre enviar:
  - `Authorization: Bearer <access>`
  - `X-Tenant-ID`
- Implementar:
  - `request_id` para idempotência (fiscal).
  - `local_tx_uuid` para idempotência de sync offline.

---

## 7. Comunicação entre Componentes

### 7.1 Diagrama de alto nível (conceitual)

```mermaid
flowchart LR
  PDV[App PDV / SmartPOS] -->|HTTPS /api/v1| NGINX
  FRONT[Frontend Web] -->|HTTPS /api/v1| NGINX
  NGINX --> BACKEND[Backend Django / DRF]
  BACKEND --> DB[(PostgreSQL Multi-tenant)]
  INFRA[Infra (Terraform/CI/Compose)] --> NGINX
  INFRA --> BACKEND
  INFRA --> DB
