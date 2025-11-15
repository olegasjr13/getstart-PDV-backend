# Arquitetura Geral do Backend

## Visão Macro

- **Linguagem**: Python 3.x
- **Framework**: Django + Django REST Framework
- **Banco**: PostgreSQL multi-tenant (django-tenants)
- **Autenticação**: JWT (SimpleJWT), com claims de `user_id`, `perfil`, `filial_id`, `terminal_id`.
- **Domínios (apps)**:
  - `tenants`: multi-tenancy (schemas, domains).
  - `usuario`: usuários, perfis, PIN, RBAC.
  - `filial`: dados fiscais da empresa (CNPJ, IE, UF, A1, CSC).
  - `terminal`: terminais lógicos (SmartPOS).
  - `fiscal`: NFC-e (reserva, pré-emissão, emissão, cancelamento).
  - `produto` / `codigobarras`: catálogo e códigos de barras.
  - `caixa`: sessão de caixa e movimentos.
  - `pagamentos`: TEF, Pix, multi-meio.
  - `sync`: sync offline, outbox.

## Fluxos Principais

- Login:
  - `/auth/login` → gera `access` + `refresh` e contextos de filial+terminal.
- Fiscal:
  - `/fiscal/nfce/reservar-numero` → reserva sequencial.
  - `/fiscal/nfce/pre-emissao` → registra payload da venda.
  - `/fiscal/nfce/emissao` → gera XML e DANFE (mock por enquanto).
  - `/fiscal/nfce/cancelar` → cancela documento com estorno obrigatório.
- Offline:
  - `/sync/outbox` → recebe eventos com `local_tx_uuid` (idempotente).

## Princípios

- **Idempotência** em tudo que pode reprocessar (request_id, local_tx_uuid).
- **Separação de domínios** por app.
- **Multi-tenant por schema** (isolamento forte de dados).
- **Logs estruturados** com contexto fiscal: `tenant_id`, `filial_id`, `terminal_id`, `request_id`, `numero`, `serie`.
