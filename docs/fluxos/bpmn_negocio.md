# Fluxos de Negócio — GetStart PDV (BPMN Lógico)

Este documento descreve os **principais fluxos de negócio** do GetStart PDV em nível de processo, usando notação inspirada em BPMN (em texto) e diagramas `mermaid`.

Fluxos cobertos:

1. Fluxo de Login (Operador no PDV)
2. Fluxo de Venda + Emissão NFC-e
3. Fluxo de Cancelamento NFC-e
4. Fluxo de Sync/Outbox (Offline → Online)
5. Fluxo de Abertura/Fechamento de Caixa

---

## 1. Fluxo de Login (Operador PDV)

### 1.1 Objetivo

Garantir que apenas usuários autorizados, vinculados ao tenant e filial corretos, consigam operar o PDV.

### 1.2 Passos (Narrativa BPMN)

1. Operador informa **e-mail/usuário + senha + tenant**.
2. PDV envia `POST /auth/login` com credenciais.
3. Backend:
   - Valida tenant (`X-Tenant-ID` / body).
   - Busca usuário.
   - Verifica senha (hash).
   - Verifica se usuário está ativo.
   - Verifica vínculo com filial (se aplicável).
4. Se tudo OK:
   - Gera `access_token` + `refresh_token`.
   - Registra log de login.
   - Retorna tokens + dados do usuário.
5. Se falha:
   - Incrementa contador de falha.
   - Em caso de excesso, aplica bloqueio temporário.
   - Retorna erro `AUTH_1000` ou `AUTH_1001`.

### 1.3 Diagrama (mermaid)

```mermaid
flowchart TD
    A[Operador insere credenciais no PDV] --> B[PDV envia POST /auth/login]
    B --> C[Backend valida tenant]
    C --> D[Backend busca usuário]
    D --> E{Usuário existe e ativo?}
    E -- Não --> E1[Retorna AUTH_1000 ou AUTH_1001<br/>Incrementa tentativas] --> Z[Fim - Login Negado]
    E -- Sim --> F[Valida senha (hash)]
    F --> G{Senha ok?}
    G -- Não --> G1[Retorna AUTH_1000] --> Z
    G -- Sim --> H[Gera access_token e refresh_token]
    H --> I[Registra log de login]
    I --> J[Retorna tokens ao PDV]
    J --> K[PDV armazena tokens em memória/armazenamento seguro]
    K --> L[Operador autenticado]
2. Fluxo de Venda + Emissão NFC-e
2.1 Visão Geral

Fluxo completo da venda:

Operador registra itens no PDV.

PDV calcula totais.

PDV reserva numeração.

PDV envia pré-emissão (payload completo).

PDV solicita emissão NFC-e (mock ou SEFAZ real).

NFC-e emitida e DANFE disponível.

2.2 Passos Detalhados

Registro da venda (lado PDV)

Leitura de código de barras / seleção de produto.

Definição de quantidade, descontos, acréscimos.

Cálculo de totais.

Reserva de numeração

PDV gera request_id (UUID).

Chama POST /fiscal/nfce/reserva com:

filial_id, terminal_id, serie, request_id.

Backend:

Valida terminal + filial + A1.

Verifica se já existe reserva com request_id.

Se não existir, calcula próximo número sequencial.

Persiste NfceNumeroReserva.

Log: nfce_reserva_numero.

Pré-emissão

PDV monta payload completo da venda.

Chama POST /fiscal/nfce/pre-emissao com:

request_id + itens + pagamentos + totais.

Backend:

Garante existência da reserva para request_id.

Valida consistência de totais.

Persiste payload em NfcePreEmissao.

Log: nfce_pre_emissao.

Emissão

PDV chama POST /fiscal/nfce/emissao com request_id.

Backend:

Busca NfcePreEmissao.

Gera XML mock (ou real).

Gera chave, protocolo.

Persiste documento fiscal.

Log: nfce_emissao.

Retorno para PDV

Backend devolve:

numero, serie, chave, xml, danfe_base64.

PDV:

Exibe confirmação.

Envia DANFE para impressão / exibição QRCode.

2.3 Diagrama (mermaid)
sequenceDiagram
    participant OP as Operador
    participant PDV as PDV (App)
    participant API as Backend API
    participant DB as Banco (tenant)

    OP->>PDV: Registra itens, descontos, pagamentos
    PDV->>PDV: Calcula totais da venda

    PDV->>API: POST /fiscal/nfce/reserva (request_id, filial, terminal, serie)
    API->>DB: Valida terminal, filial, A1, sequencia
    DB-->>API: Numero reservado (nNF)
    API-->>PDV: { numero, serie }

    PDV->>API: POST /fiscal/nfce/pre-emissao (request_id, itens, totais, pagamentos)
    API->>DB: Valida consistência e grava NfcePreEmissao
    API-->>PDV: OK

    PDV->>API: POST /fiscal/nfce/emissao (request_id)
    API->>DB: Busca pré-emissão
    API->>API: Gera XML + chave + protocolo (mock ou SEFAZ)
    API->>DB: Persiste documento fiscal
    API-->>PDV: { chave, xml, danfe_base64 }

    PDV->>OP: Exibe sucesso / imprime DANFE

3. Fluxo de Cancelamento NFC-e
3.1 Objetivo

Garantir que nenhuma NFC-e seja cancelada sem estorno financeiro prévio e que todo fluxo seja rastreável.

3.2 Passos

Operador solicita cancelamento de uma venda (por chave / número).

PDV solicita:

Estorno de pagamento (TEF/Pix) e registra estorno em caixa.

PDV chama POST /fiscal/nfce/cancelar com:

chave, justificativa.

Backend:

Verifica se NFC-e existe e está em status AUTORIZADA.

Verifica se há estorno financeiro vinculado.

Se não houver → FISCAL_4020.

Em modo mock:

Gera protocolo de cancelamento simulado.

Em modo real:

Envia evento de cancelamento à SEFAZ.

Atualiza status para CANCELADA.

Registra log nfce_cancelamento.

3.3 Diagrama (mermaid)
flowchart TD
    A[Operador solicita cancelamento] --> B[PDV verifica venda/NFC-e]
    B --> C[PDV executa estorno financeiro<br/>(TEF/Pix/caixa)]
    C --> D[PDV chama POST /fiscal/nfce/cancelar]
    D --> E[Backend valida NFC-e e status]
    E --> F{Estorno financeiro registrado?}
    F -- Não --> F1[Erro FISCAL_4020] --> Z[Fim - Cancelamento negado]
    F -- Sim --> G[Backend gera cancelamento (mock ou SEFAZ)]
    G --> H[Atualiza status NFC-e para CANCELADA]
    H --> I[Registra log nfce_cancelamento]
    I --> J[Retorna sucesso ao PDV]
    J --> K[PDV registra em tela/comprovante]

4. Fluxo de Sync/Outbox (Offline → Online)
4.1 Objetivo

Garantir que operações feitas offline no PDV sejam sincronizadas de forma idempotente e ordenada.

4.2 Passos

PDV opera offline (sem conexão).

Eventos são salvos localmente:

Cada evento tem local_tx_uuid.

Quando a conexão volta:

PDV envia lote de eventos para /sync/outbox.

Backend:

Para cada evento:

Verifica se local_tx_uuid já foi processado.

Se sim → ignora (idempotência).

Se não:

Processa evento:

VENDA_FINALIZADA → chama internamente fluxo fiscal.

CANCELAMENTO → chama fluxo de cancelamento.

MOVIMENTO_CAIXA → registra em caixa.

Retorna resultado por evento (status + mensagem).

PDV registra quais eventos foram sincronizados.

4.3 Diagrama (mermaid)
sequenceDiagram
    participant PDV as PDV Offline
    participant API as Backend
    participant DB as Banco

    PDV->>PDV: Registra operações localmente (eventos com local_tx_uuid)
    PDV->>API: POST /sync/outbox (lista de eventos)
    API->>DB: Para cada evento, consulta SyncEvento por local_tx_uuid
    alt Já processado
        API-->>API: Ignora, marca como duplicado
    else Novo evento
        API->>API: Processa evento (VENDA, CANCELAMENTO, CAIXA, etc.)
        API->>DB: Persiste resultado e marca como processado
    end
    API-->>PDV: Lista de resultados por evento
    PDV->>PDV: Marca eventos como sincronizados

5. Fluxo de Abertura/Fechamento de Caixa
5.1 Abertura

Operador ou gerente solicita abertura.

PDV chama POST /caixa/abrir.

Backend:

Verifica se existe sessão de caixa aberta para aquele terminal/operador.

Se não:

Cria CaixaSessao com status ABERTO.

Log: caixa_abertura.

5.2 Fechamento

Operador/gerente solicita fechamento.

PDV chama POST /caixa/fechar.

Backend:

Calcula totais (venda, estorno, sangria, suprimento).

Compara com valor informado pelo operador.

Persiste fechamento e status FECHADO.

Log: caixa_fechamento.
