# GetStart PDV — Fluxos Técnicos e Diagramas

## 1. Fluxo de Login

```mermaid
sequenceDiagram
  participant PDV as App PDV
  participant API as Backend API
  participant DB as DB Tenant

  PDV->>API: POST /auth/login (username, password, terminal_id)
  API->>DB: Valida usuário e vínculo user↔filial↔terminal
  DB-->>API: Usuário válido
  API-->>PDV: 200 (access_token, refresh_token, perfil, filial_id, terminal_id)
```

## 2. Fluxo de Reserva de Numeração NFC-e

```mermaid
sequenceDiagram
  participant PDV
  participant API
  participant DB

  PDV->>API: POST /fiscal/nfce/reservar-numero (terminal_id, serie, request_id)
  API->>DB: Busca terminal e filial
  API->>DB: Valida vínculo usuário↔filial
  API->>DB: Verifica A1 (não expirado)
  API->>DB: Inicia transação
  API->>DB: SELECT NfceNumeroReserva WHERE request_id = ?
  alt reserva já existe
    DB-->>API: Reserva existente
    API-->>PDV: Número já reservado (idempotente)
  else primeira vez
    API->>DB: SELECT MAX(numero) WHERE terminal_id, serie FOR UPDATE
    API->>DB: INSERT NfceNumeroReserva (numero = max+1)
    DB-->>API: OK
    API-->>PDV: 200 (novo número)
  end
```

## 3. Fluxo de Pré-Emissão

```mermaid
sequenceDiagram
  participant PDV
  participant API
  participant DB

  PDV->>API: POST /fiscal/nfce/pre-emissao (request_id, payload)
  API->>DB: Busca NfceNumeroReserva por request_id
  API->>DB: Verifica A1
  API->>DB: get_or_create NfcePreEmissao (request_id)
  API-->>PDV: 200 (dados da pré-emissão)
```

## 4. Fluxo de Emissão (Mock)

```mermaid
sequenceDiagram
  participant PDV
  participant API
  participant DB

  PDV->>API: POST /fiscal/nfce/emissao (request_id)
  API->>DB: Carrega NfcePreEmissao
  API->>API: Gera XML mock (NFC-e)
  API->>DB: Persiste NFC-e e NfceLog
  API-->>PDV: 200 (xml, danfe_base64)
```

## 5. Fluxo de Cancelamento

```mermaid
sequenceDiagram
  participant PDV
  participant API
  participant DB

  PDV->>API: POST /fiscal/nfce/cancelar (chave, justificativa)
  API->>DB: Verifica estorno financeiro da venda
  API->>DB: Verifica prazo de cancelamento
  API->>API: Envia evento de cancelamento (mock/SEFAZ)
  API->>DB: Atualiza status da NFC-e para CANCELADA
  API-->>PDV: 200 (cancelamento registrado)
```

## 6. Fluxo de Sync Offline (Outbox)

```mermaid
sequenceDiagram
  participant PDV
  participant API
  participant DB

  loop Periódico
    PDV->>API: POST /sync/outbox (lista de eventos com local_tx_uuid)
    API->>DB: Para cada evento: verifica se local_tx_uuid já existe
    alt Já existe
      API->>DB: Ignora (idempotente)
    else Novo
      API->>DB: Insere sync_evento e processa
    end
    API-->>PDV: 200 (resultado por evento)
  end
```
