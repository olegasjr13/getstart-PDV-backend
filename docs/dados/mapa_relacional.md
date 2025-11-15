# Mapa Relacional de Dados — GetStart PDV

Este documento apresenta uma visão relacional das tabelas principais do backend, complementando o `dicionario_dados.md`.

---

## 1. Visão Geral (Alta Nível)

Grupos de tabelas:

- **Tenancy (schema público)**:
  - `tenants_tenant`
  - `tenants_domain`
- **Domínio Fiscal (por tenant)**:
  - `filial_filial`
  - `terminal_terminal`
  - `fiscal_nfcenumeroreserva`
  - `fiscal_nfcepreemissao`
  - (futuro) `fiscal_nfcedocumento`, `fiscal_nfcelog`
- **Usuário e Acesso**:
  - `usuario_user`
  - `usuario_userfilial`
- **Produtos e Catálogo**:
  - `produto_produto`
  - `codigobarras_codigo`
- **Caixa e Pagamentos**:
  - `caixa_caixasesao`
  - `caixa_caixamovimento`
  - `pagamentos_transacao`
- **Sync Offline**:
  - `sync_evento`

---

## 2. Diagrama Conceitual (Mermaid ER)

```mermaid
erDiagram
  TENANT ||--o{ DOMAIN : "possui"
  TENANT {
    uuid id
    string cnpj_raiz
  }
  DOMAIN {
    uuid id
    string domain
  }

  FILIAL ||--o{ TERMINAL : "possui"
  FILIAL ||--o{ USERFILIAL : "vincula usuários"
  FILIAL {
    uuid id
    string cnpj
    string uf
  }
  TERMINAL {
    uuid id
    uuid filial_id
  }

  USER ||--o{ USERFILIAL : "pode estar em várias filiais"
  USER {
    int id
    string username
  }
  USERFILIAL {
    uuid id
    int user_id
    uuid filial_id
  }

  TERMINAL ||--o{ NFCENUMERORESERVA : "gera reservas"
  FILIAL ||--o{ NFCENUMERORESERVA : "por filial"
  NFCENUMERORESERVA ||--|| NFCEPREEMISSAO : "1:1 por request_id"
  NFCENUMERORESERVA {
    uuid id
    uuid filial_id
    uuid terminal_id
    int numero
    int serie
    uuid request_id
  }
  NFCEPREEMISSAO {
    uuid id
    uuid filial_id
    uuid terminal_id
    int numero
    int serie
    uuid request_id
  }

  PRODUTO ||--o{ CODIGOBARRAS : "pode ter vários códigos"
  PRODUTO {
    uuid id
    string codigo_interno
  }
  CODIGOBARRAS {
    uuid id
    uuid produto_id
    string codigo_barras
  }

  USER ||--o{ CAIXASESAO : "abre sessões"
  TERMINAL ||--o{ CAIXASESAO : "por terminal"
  FILIAL ||--o{ CAIXASESAO : "por filial"
  CAIXASESAO ||--o{ CAIXAMOVIMENTO : "tem movimentos"
  CAIXASESAO {
    uuid id
    int user_id
    uuid terminal_id
    uuid filial_id
  }
  CAIXAMOVIMENTO {
    uuid id
    uuid sessao_id
    decimal valor
    string tipo
  }

  NFCENUMERORESERVA ||--o{ PAGAMENTO : "pode ter pagamentos" 
  PAGAMENTO {
    uuid id
    uuid venda_id
    decimal valor
  }

  SYNCEVENTO {
    uuid id
    uuid local_tx_uuid
    string event_type
  }
