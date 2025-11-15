# Domínios (Bounded Contexts) — GetStart PDV Backend

Este documento descreve os **domínios principais (apps Django)** do backend e suas responsabilidades, para facilitar entendimento e evitar acoplamentos indevidos.

---

## 1. Visão geral

Domínios principais:

- `tenants` — Multi-tenancy por schema.
- `usuario` — Usuários e RBAC.
- `filial` — Dados fiscais da empresa.
- `terminal` — Terminais (PDVs).
- `fiscal` — NFC-e (reserva, pré-emissão, emissão, cancelamento).
- `produto` / `codigobarras` — Catálogo de produtos.
- `caixa` — Sessão de caixa e movimentos.
- `pagamentos` — Transações financeiras (TEF, Pix etc.).
- `sync` — Eventos offline e outbox.

---

## 2. Domínio `tenants`

**Responsabilidade:**  
Controlar o isolamento de dados entre clientes por meio de schemas PostgreSQL (multi-tenant).

**Principais modelos:**

- `Tenant` (`tenants_tenant`):
  - `cnpj_raiz`
  - `nome`
  - `is_active`
- `Domain` (`tenants_domain`):
  - `domain`
  - `tenant`
  - `is_primary`

**Regras chave:**

- Cada tenant possui um schema próprio no banco.
- O middleware seleciona o schema com base em:
  - `X-Tenant-ID` (CNPJ raiz).
- Migrations são aplicadas por schema via `django-tenants`.

---

## 3. Domínio `usuario`

**Responsabilidade:**  
Usuários, autenticação e autorização de alto nível.

**Principais modelos:**

- `User`:
  - `username`, `password`, `email`.
  - `perfil` (`OPERADOR`, `SUPERVISOR`, `GERENTE`, `ADMIN`).
  - `pin_hash`.
- `UserFilial`:
  - liga usuário a Filiais específicas.

**Endpoint chave:**

- `/auth/login`
- `/auth/refresh`
- (futuro) `/auth/validar-pin`

**Regras:**

- Apenas usuários ativos (`is_active = True`) podem autenticar.
- A associação de um usuário com uma ou mais filiais é feita via `UserFilial`.
- PIN é exigido para operações sensíveis (caixa, cancelamento etc., quando implementado).

---

## 4. Domínio `filial`

**Responsabilidade:**  
Dados fiscais da empresa emitente (Filial).

**Principais campos:**

- `cnpj`, `ie`, `razao_social`, `nome_fantasia`.
- `uf`, `regime_tributario`.
- `csc_id`, `csc_token`.
- `a1_pfx` (certificado A1 criptografado).
- `a1_expires_at`.
- `ambiente` (`homologacao` ou `producao`).

**Regras:**

- Uma Filial é o **ponto de verdade** para:
  - Ambientes fiscais.
  - Certificado A1.
  - CSC.
- Operações fiscais consultam Filial para validar:
  - A1 presente e válido.
  - Ambiente correto.

---

## 5. Domínio `terminal`

**Responsabilidade:**  
Gerenciar terminais (PDVs) físicos/lógicos.

**Principais campos:**

- `filial` (FK).
- `identificador` (número de série ou ID do dispositivo).
- `descricao`.
- `serie` (série fiscal padrão).
- `numero_atual` (espelho, não fonte de verdade).

**Regras:**

- Terminal sempre ligado a uma Filial.
- Série do terminal é usada na reserva NFC-e.
- `numero_atual` pode ser atualizado a partir de operações fiscais para fins de monitoramento, mas a numeração oficial está em `NfceNumeroReserva`.

---

## 6. Domínio `fiscal`

**Responsabilidade:**  
Coração fiscal do PDV (NFC-e).

**Principais modelos:**

- `NfceNumeroReserva`:
  - Reserva de números (sequência).
- `NfcePreEmissao`:
  - Armazena payload da venda.
- (Futuro) `NfceDocumento`:
  - XML, status (`AUTORIZADA`, `CANCELADA`, `REJEITADA`).
- (Futuro) `NfceLog`:
  - Eventos de reserva, emissão, cancelamento.

**Principais endpoints:**

- `POST /fiscal/nfce/reservar-numero`
- `POST /fiscal/nfce/pre-emissao`
- `POST /fiscal/nfce/emissao`
- `POST /fiscal/nfce/cancelar`

**Regras chave:**

- Numeração sequencial por Filial + Terminal + Série.
- Idempotência por `request_id`.
- A1 é obrigatório e validado em cada etapa.

Complemento: ver `docs/fiscal/regras_fiscais.md`.

---

## 7. Domínio `produto` / `codigobarras`

**Responsabilidade:**  
Catálogo de produtos e códigos de barras.

**Principais modelos:**

- `Produto`:
  - `codigo_interno`, `descricao`, `unidade`, `preco_venda`.
  - `versao_catalogo`, `is_tombstone`.
- `CodigoBarras`:
  - `produto`, `codigo_barras`, `principal`.

**Regras:**

- Sync incremental baseado em `versao_catalogo`.
- Exclusão lógica via `is_tombstone`.
- Produto pode ter diversos códigos de barras.

---

## 8. Domínio `caixa`

**Responsabilidade:**  
Controle de sessão de caixa e movimentos.

**Principais modelos:**

- `CaixaSessao`:
  - `user`, `filial`, `terminal`.
  - `aberto_em`, `fechado_em`.
  - `status`.
- `CaixaMovimento`:
  - `sessao`, `tipo`, `valor`, `forma_pagto`.

**Regras:**

- Uma sessão aberta por usuário + terminal de cada vez.
- Movimentos de suprimento, sangria, recebimento etc.
- Estornos para cancelamento fiscal devem ser rastreáveis aqui.

---

## 9. Domínio `pagamentos`

**Responsabilidade:**  
Transações TEF, Pix, etc. (alguns pontos futuros).

**Principais campos:**

- `venda_id`, `tipo` (`TEF`, `PIX`, `DINHEIRO`, etc.).
- `valor`, `nsu`, `autorizacao`, `bandeira`, `parcelas`.
- `status` (`PENDENTE`, `APROVADA`, `NEGADA`, `CANCELADA`).

**Regras:**

- Deve haver vínculo claro entre:
  - NFC-e ↔ Pagamento(s) ↔ CaixaMovimento.
- Estornos devem ser rastreáveis para permitir cancelamento fiscal.

---

## 10. Domínio `sync`

**Responsabilidade:**  
Sincronização offline via eventos.

**Modelo principal:**

- `SyncEvento`:
  - `local_tx_uuid`, `event_type`, `payload`, `status`.

**Regras:**

- `local_tx_uuid` garante idempotência.
- Eventos são processados posteriormente:
  - Criação de vendas.
  - Cancelamentos.
  - Outros.

---

## 11. Recomendações de acoplamento

- `fiscal` não deve depender diretamente de UI ou lógica do PDV.
- `fiscal` consome dados de:
  - `filial`, `terminal`, `caixa`, `pagamentos`, `produto`.
- `sync` atua como fronteira de integração com clientes offline:
  - Ele não deve conter regra fiscal pesada.
  - Apenas orquestrar processamento de eventos no domínio correto.

