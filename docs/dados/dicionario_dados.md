# GetStart PDV — Dicionário de Dados (Backend)

## 1. Convenções Gerais

- UUID: identificador único em formato UUIDv4.
- DateTime: `YYYY-MM-DDTHH:MM:SSZ` (UTC) ou timezone-aware.
- Money: decimal com 2 casas decimais, armazenado como DECIMAL(15,2).
- Boolean: `true` / `false`.

---

## 2. Domínio Tenancy

### 2.1 Tabela: tenants_tenant (PUBLIC)

| Campo            | Tipo      | Obrigatório | Descrição                                                                 |
|------------------|-----------|------------:|---------------------------------------------------------------------------|
| id               | UUID      | Sim         | Identificador único do tenant.                                            |
| cnpj_raiz        | String(14)| Sim         | CNPJ raiz do cliente (somente números).                                   |
| nome             | String(255)| Sim        | Nome comercial / razão social simplificada.                               |
| premium_db_alias | String(64)| Não         | Alias de banco premium (opcional, para sharding).                         |
| created_at       | DateTime  | Sim         | Data/hora de criação do tenant.                                           |
| is_active        | Boolean   | Sim         | Indica se o tenant está ativo.                                            |

### 2.2 Tabela: tenants_domain (PUBLIC)

| Campo      | Tipo        | Obrigatório | Descrição                                        |
|------------|-------------|------------:|--------------------------------------------------|
| id         | UUID        | Sim         | Identificador do domínio.                        |
| domain     | String(255) | Sim         | Host (ex: clienteX.getstartpdv.com).             |
| tenant_id  | UUID (FK)   | Sim         | Referência a tenants_tenant.id.                  |
| is_primary | Boolean     | Sim         | Se este domínio é o principal do tenant.         |

---

## 3. Domínio Usuário & RBAC

### 3.1 Tabela: usuario_user

| Campo       | Tipo          | Obrig. | Descrição                                                           |
|-------------|---------------|-------:|---------------------------------------------------------------------|
| id          | Integer (PK)  | Sim    | Identificador interno do usuário.                                  |
| username    | String(150)   | Sim    | Login do usuário. Único por schema.                                |
| password    | Hash          | Sim    | Hash de senha, conforme Django (`pbkdf2` ou `argon2`).              |
| email       | String(254)   | Não    | E-mail do usuário.                                                 |
| perfil      | String(20)    | Sim    | PERFIL: `OPERADOR`, `SUPERVISOR`, `GERENTE`, `ADMIN`.              |
| pin_hash    | String(255)   | Não    | Hash do PIN (PBKDF2/Argon2).                                       |
| is_active   | Boolean       | Sim    | Indica se usuário está ativo.                                      |
| last_login  | DateTime      | Não    | Último login registrado.                                           |
| date_joined | DateTime      | Sim    | Data/hora de criação.                                              |

### 3.2 Tabela: usuario_userfilial

| Campo      | Tipo   | Obrig. | Descrição                                      |
|------------|--------|-------:|------------------------------------------------|
| id         | UUID   | Sim    | Identificador do vínculo.                      |
| user_id    | Int FK | Sim    | Ref. a usuario_user.id.                        |
| filial_id  | UUID FK| Sim    | Ref. a filial_filial.id.                       |
| created_at | DateTime| Sim   | Data de criação do vínculo.                    |

---

## 4. Domínio Filial

### 4.1 Tabela: filial_filial

| Campo            | Tipo          | Obrig. | Descrição                                                                      |
|------------------|---------------|-------:|--------------------------------------------------------------------------------|
| id               | UUID          | Sim    | Identificador da filial.                                                       |
| cnpj             | String(14)    | Sim    | CNPJ completo (somente números).                                               |
| ie               | String(20)    | Não    | Inscrição Estadual, se aplicável.                                              |
| razao_social     | String(255)   | Sim    | Razão social completa.                                                         |
| nome_fantasia    | String(255)   | Não    | Nome fantasia.                                                                 |
| uf               | String(2)     | Sim    | Unidade federativa (ex: SP, MG).                                               |
| regime_tributario| String(30)    | Sim    | Regime (`SIMPLES`, `NORMAL`, etc.).                                            |
| csc_id           | String(20)    | Não    | Identificador do CSC da SEFAZ.                                                 |
| csc_token        | String(255)   | Não    | Token secreto do CSC (armazenado de forma segura).                             |
| a1_pfx           | Blob/Encrypted| Não    | Certificado A1 em formato PFX, criptografado.                                  |
| a1_expires_at    | DateTime      | Não    | Data de expiração do A1.                                                       |
| ambiente         | String(15)    | Sim    | `homologacao` ou `producao`.                                                   |
| created_at       | DateTime      | Sim    | Data de criação.                                                               |

---

## 5. Domínio Terminal

### 5.1 Tabela: terminal_terminal

| Campo              | Tipo        | Obrig. | Descrição                                                              |
|--------------------|-------------|-------:|------------------------------------------------------------------------|
| id                 | UUID        | Sim    | Identificador do terminal.                                             |
| filial_id          | UUID FK     | Sim    | Ref. a filial_filial.id.                                              |
| identificador      | String(100) | Sim    | Identificador lógico/físico do dispositivo (ex: número de série).      |
| descricao          | String(255) | Não    | Texto descritivo.                                                      |
| serie              | Integer     | Sim    | Série fiscal padrão para NFC-e.                                       |
| numero_atual       | Integer     | Não    | Último número emitido **espelhado** (não é a fonte de verdade).       |
| permite_suprimento | Boolean     | Sim    | Se terminal permite lançar suprimento.                                |
| permite_sangria    | Boolean     | Sim    | Se terminal permite lançar sangria.                                   |
| created_at         | DateTime    | Sim    | Data de criação.                                                      |

---

## 6. Domínio Fiscal – NFC-e

### 6.1 Tabela: fiscal_nfcenumeroreserva

| Campo       | Tipo      | Obrig. | Descrição                                                                   |
|-------------|-----------|-------:|-----------------------------------------------------------------------------|
| id          | UUID      | Sim    | Identificador da reserva de número.                                        |
| filial_id   | UUID FK   | Sim    | Filial onde o documento será emitido.                                      |
| terminal_id | UUID FK   | Sim    | Terminal da emissão.                                                       |
| serie       | Integer   | Sim    | Série da NFC-e.                                                             |
| numero      | Integer   | Sim    | Número sequencial reservado.                                               |
| request_id  | UUID      | Sim    | Identificador idempotente do request. Único por terminal+serie.            |
| reserved_at | DateTime  | Sim    | Data/hora da reserva.                                                       |

Índices:
- Único: (terminal_id, serie, numero).
- Único: (request_id).

### 6.2 Tabela: fiscal_nfcepreemissao

| Campo       | Tipo      | Obrig. | Descrição                                                   |
|-------------|-----------|-------:|-------------------------------------------------------------|
| id          | UUID      | Sim    | Identificador da pré-emissão.                              |
| filial_id   | UUID FK   | Sim    | Filial.                                                     |
| terminal_id | UUID FK   | Sim    | Terminal.                                                   |
| serie       | Integer   | Sim    | Série.                                                      |
| numero      | Integer   | Sim    | Número da NFC-e.                                            |
| request_id  | UUID      | Sim    | Mesmo request_id da reserva.                               |
| payload     | JSON      | Sim    | Conteúdo da venda (itens, totais, pagamentos).             |
| created_at  | DateTime  | Sim    | Data/hora de criação.                                      |

Índices:
- Único: (request_id).
- Index: (filial_id, terminal_id, serie, numero).

---

## 7. Domínio Produtos

### 7.1 Tabela: produto_produto

| Campo           | Tipo        | Obrig. | Descrição                                             |
|-----------------|-------------|-------:|-------------------------------------------------------|
| id              | UUID        | Sim    | Identificador do produto.                             |
| codigo_interno  | String(50)  | Sim    | Código interno único.                                 |
| descricao       | String(255) | Sim    | Descrição do produto.                                 |
| unidade         | String(10)  | Sim    | Unidade de medida (UN, KG, CX, etc.).                 |
| preco_venda     | Money       | Sim    | Preço de venda.                                       |
| ativo           | Boolean     | Sim    | Indica se produto está ativo.                         |
| versao_catalogo | Integer     | Sim    | Versão do catálogo em que foi alterado por último.    |
| is_tombstone    | Boolean     | Sim    | Marca exclusão lógica para sync incremental.          |
| updated_at      | DateTime    | Sim    | Última atualização.                                   |

### 7.2 Tabela: codigobarras_codigo

| Campo           | Tipo     | Obrig. | Descrição                                    |
|-----------------|----------|-------:|----------------------------------------------|
| id              | UUID     | Sim    | Identificador do código de barras.           |
| produto_id      | UUID FK  | Sim    | Produto referenciado.                        |
| codigo_barras   | String(50)| Sim   | EAN/GTIN ou código interno de leitura.       |
| principal       | Boolean  | Sim    | Se é o código principal.                     |

---

## 8. Domínio Caixa

### 8.1 Tabela: caixa_caixasesao

| Campo       | Tipo     | Obrig. | Descrição                                                      |
|-------------|----------|-------:|----------------------------------------------------------------|
| id          | UUID     | Sim    | Identificador da sessão.                                      |
| user_id     | Int FK   | Sim    | Usuário que abriu o caixa.                                    |
| terminal_id | UUID FK  | Sim    | Terminal utilizado.                                           |
| filial_id   | UUID FK  | Sim    | Filial.                                                       |
| aberto_em   | DateTime | Sim    | Data/hora da abertura.                                       |
| fechado_em  | DateTime | Não    | Data/hora de fechamento (null enquanto em aberto).           |
| status      | String(20)| Sim   | `ABERTO` ou `FECHADO`.                                       |

Regra:
- Único: sessão ativa por (user_id, terminal_id).

### 8.2 Tabela: caixa_caixamovimento

| Campo        | Tipo      | Obrig. | Descrição                                               |
|--------------|-----------|-------:|---------------------------------------------------------|
| id           | UUID      | Sim    | Identificador do movimento.                             |
| sessao_id    | UUID FK   | Sim    | Sessão de caixa.                                       |
| tipo         | String(20)| Sim    | `ABERTURA`, `SUPRIMENTO`, `SANGRIA`, `RECEBIMENTO`, etc.|
| valor        | Money     | Sim    | Valor da operação.                                     |
| forma_pagto  | String(20)| Não    | `DINHEIRO`, `TEF`, `PIX`, etc.                         |
| created_at   | DateTime  | Sim    | Data/hora do lançamento.                               |

---

## 9. Domínio Pagamentos

### 9.1 Tabela: pagamentos_transacao

| Campo         | Tipo      | Obrig. | Descrição                                                       |
|---------------|-----------|-------:|-----------------------------------------------------------------|
| id            | UUID      | Sim    | Identificador da transação.                                    |
| venda_id      | UUID FK   | Sim    | Referência à venda/nota.                                       |
| tipo          | String(10)| Sim    | `TEF`, `PIX`, `DINHEIRO`, etc.                                 |
| valor         | Money     | Sim    | Valor da transação.                                            |
| nsu           | String(50)| Não    | NSU retornado pelo adquirente (TEF).                           |
| autorizacao   | String(50)| Não    | Código de autorização.                                         |
| bandeira      | String(20)| Não    | Bandeira do cartão.                                            |
| parcelas      | Integer   | Não    | Quantidade de parcelas, se aplicável.                          |
| status        | String(20)| Sim    | `PENDENTE`, `APROVADA`, `NEGADA`, `CANCELADA`.                 |
| created_at    | DateTime  | Sim    | Data/hora da criação.                                          |

---

## 10. Domínio Sync Offline

### 10.1 Tabela: sync_evento

| Campo         | Tipo      | Obrig. | Descrição                                                 |
|---------------|-----------|-------:|-----------------------------------------------------------|
| id            | UUID      | Sim    | Identificador do evento.                                  |
| local_tx_uuid | UUID      | Sim    | Identificador originado no PDV (para dedupe).             |
| event_type    | String(50)| Sim    | Tipo de evento (`VENDA`, `CANCELAMENTO`, etc.).           |
| payload       | JSON      | Sim    | Conteúdo do evento.                                       |
| status        | String(20)| Sim    | `PENDENTE`, `PROCESSADO`, `ERRO`.                         |
| created_at    | DateTime  | Sim    | Data/hora de registro.                                    |
| processed_at  | DateTime  | Não    | Data/hora de processamento.                               |
