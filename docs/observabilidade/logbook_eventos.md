# Logbook de Eventos — GetStart PDV

## 1. Objetivo

Este documento define o **catálogo oficial de eventos de log** do backend do GetStart PDV.

Ele responde às perguntas:

- **O que** deve ser logado? (quais eventos de negócio importam)
- **Como** esses eventos devem ser nomeados? (campo `event` dos logs)
- **Quando** o evento deve ser emitido? (em qual ponto do fluxo)
- Se o evento gera apenas **log JSON** ou também **registro de auditoria em banco**.

> Os detalhes de formato de log, campos obrigatórios e integração com Sentry estão em
> `docs/observabilidade/padroes_logs_backend.md`.
> Aqui o foco é o **catálogo de eventos de negócio**.

---

## 2. Convenções Gerais

- Cada evento de log possui um identificador único no campo `event` do log JSON.
- O `logger` utilizado deve ser adequado ao domínio, por exemplo:
  - `pdv.fiscal` para eventos fiscais (NFC-e).
  - `pdv.auth` para autenticação/segurança.
  - `pdv.tenant` para contexto multi-tenant.
- Sempre que possível, o evento deve conter em `extra`:
  - `tenant_id` (CNPJ raiz).
  - `schema_name`.
  - `filial_id`.
  - `terminal_id`.
  - `user_id`.
  - `request_id`.
  - Campos de negócio relevantes (número da NFC-e, chave, etc.).

Além dos logs JSON, alguns eventos também geram **auditoria em banco de dados** (por exemplo, emissão de NFC-e). Esses casos estão sinalizados abaixo.

---

## 3. Eventos — Domínio Fiscal (NFC-e)

### 3.1. Reserva de Número

**`nfce_reserva_numero`**

- **Descrição**:
  Emissão de log quando um número de NFC-e é reservado para um terminal/série, através do fluxo de reserva (`NfceNumeroReserva`).

- **Momento do log**:
  Após reserva bem-sucedida (antes de retornar resposta para o cliente).

- **Sugestão de payload (extra)**:
  - `tenant_id`
  - `filial_id`
  - `terminal_id`
  - `user_id`
  - `request_id`
  - `numero`
  - `serie`
  - `uf`

- **Auditoria em DB**:
  - Em regra, não é obrigatório gravar auditoria específica apenas para reserva de número, desde que a emissão/gravação posterior esteja auditada.
  - Pode ser adicionada futuramente se houver requisito de trilha completa.

---

### 3.2. Pré-emissão de NFC-e

**`nfce_pre_emissao`**

- **Descrição**:
  Registro da **pré-emissão** de NFC-e (`NfcePreEmissao`) para uma combinação `(filial, terminal, numero, serie, request_id)`.

- **Momento do log**:
  - Após persistir a pré-emissão com sucesso.
  - Antes de delegar para fluxo de emissão (mock ou SEFAZ).

- **Sugestão de payload (extra)**:
  - `tenant_id`
  - `filial_id`
  - `terminal_id`
  - `user_id`
  - `request_id`
  - `numero`
  - `serie`
  - `valor_total` (se estiver disponível no payload)
  - `uf`
  - Eventual `origem` (PDV, integração externa, etc.)

- **Auditoria em DB**:
  - Pode ser integrada ao modelo de auditoria como evento de **criação de intenção de emissão**, se a trilha fiscal exigir.
  - Decisão: inicialmente, tratar apenas como **log JSON**, e auditar obrigatoriamente os eventos de emissão/cancelamento.

---

### 3.3. Emissão via MOCK (ambientes dev/QA)

**`nfce_emissao_mock_sucesso`**

- **Descrição**:
  Emissão bem-sucedida de NFC-e utilizando client **MOCK** (sem comunicação real com SEFAZ).

- **Momento do log**:
  - Após o mock retornar resultado “autorizado” e os dados de resposta terem sido processados pelo `NfceEmissaoService`.

- **Sugestão de payload (extra)**:
  - `tenant_id`, `filial_id`, `terminal_id`, `user_id`, `request_id`
  - `numero`, `serie`
  - `status` (ex.: `"AUTORIZADA"`)
  - `chave` (quando gerada no mock)
  - `ambiente` (ex.: `"mock-dev"`, `"mock-qa"`)

- **Auditoria em DB**:
  - Dependendo da necessidade, o mesmo fluxo de auditoria usado para emissão real pode ser reutilizado aqui (ex.: para ambientes QA).
  - Em dev puro, pode ser opcional.

---

**`nfce_emissao_mock_erro`**

- **Descrição**:
  Falha na emissão de NFC-e usando client MOCK.

- **Momento do log**:
  - Quando o mock lança erro ou retorna status de falha.

- **Sugestão de payload (extra)**:
  - `tenant_id`, `filial_id`, `terminal_id`, `user_id`, `request_id`
  - `numero`, `serie`
  - `error_code`
  - `error_message`
  - Detalhes adicionais úteis para debug (sem dados sensíveis).

- **Auditoria em DB**:
  - Normalmente, não se registra auditoria em DB para erro de mock, a não ser em QA onde se deseje trilha completa de cenários de erro.

---

### 3.4. Emissão via SEFAZ (ambiente real / homologação)

> Eventos abaixo correspondem ao comportamento esperado quando os **clients reais de SEFAZ por UF** forem implementados (`SefazClientSP`, `SefazClientMG`, etc.).

**`nfce_emissao_sefaz_sucesso`**

- **Descrição**:
  NFC-e **autorizada** pela SEFAZ.

- **Momento do log**:
  - Após receber resposta de autorização da SEFAZ.
  - Após persistir (ou atualizar) o documento fiscal (`NfceDocumento`) e registrar auditoria.

- **Sugestão de payload (extra)**:
  - `tenant_id`, `filial_id`, `terminal_id`, `user_id`, `request_id`
  - `numero`, `serie`
  - `chave`
  - `protocolo`
  - `status` (ex.: `"AUTORIZADA"`)
  - `uf`
  - `ambiente` (ex.: `"homolog"`, `"producao"`)

- **Auditoria em DB**: **SIM (OBRIGATÓRIO)**
  - Deve existir um registro em tabela de auditoria de NFC-e (ver `auditoria_nfce.md`), marcando que a NFC-e foi **emitida/autorizada**, com `tipo_evento = "EMISSAO"`.

---

**`nfce_emissao_sefaz_rejeitada`**

- **Descrição**:
  NFC-e **rejeitada** pela SEFAZ (ex.: código de rejeição conhecido, schema inválido, etc.).

- **Momento do log**:
  - Após receber resposta de rejeição.
  - Antes (ou depois) de aplicar qualquer política de retry/ajuste.

- **Sugestão de payload (extra)**:
  - `tenant_id`, `filial_id`, `terminal_id`, `user_id`, `request_id`
  - `numero`, `serie`
  - `uf`
  - `ambiente`
  - `status` (ex.: `"REJEITADA"`)
  - `codigo_rejeicao`
  - `motivo_rejeicao`

- **Auditoria em DB**: **SIM (RECOMENDADO)**
  - Registrar evento de rejeição com `tipo_evento = "EMISSAO_REJEITADA"` ou equivalente na tabela de auditoria.

---

**`nfce_emissao_sefaz_erro`** (erro técnico/interno)

- **Descrição**:
  Erro técnico inesperado ao tentar emitir NFC-e (timeout, indisponibilidade, exceção interna).

- **Momento do log**:
  - Em qualquer exceção não tratada no fluxo de chamada ao client SEFAZ.

- **Sugestão de payload (extra)**:
  - `tenant_id`, `filial_id`, `terminal_id`, `user_id`, `request_id`
  - `numero`, `serie`
  - `uf`
  - `ambiente`
  - `error_type`
  - `error_message`

- **Auditoria em DB**:
  - A critério do time fiscal/negócio, pode-se registrar um evento de erro técnico na trilha de auditoria para fins de compliance.

---

### 3.5. Cancelamento, Inutilização e Outros (futuro)

A serem implementados conforme os fluxos forem codados:

- **`nfce_cancelamento_sucesso`**
- **`nfce_cancelamento_falha`**
- **`nfce_inutilizacao_sucesso`**
- **`nfce_inutilizacao_falha`**
- **`nfce_segunda_via_emitida`** (reimpressão / DANFE NFC-e, se for relevante)

Todos esses devem:

- Gerar log JSON com `event` correspondente.
- Gerar auditoria em banco com `tipo_evento` adequado, conforme `auditoria_nfce.md`.

---

## 4. Eventos — Autenticação e Sessão

### 4.1. Login

**`auth_login_sucesso`**

- **Descrição**:
  Login bem-sucedido via endpoint de autenticação.

- **Momento do log**:
  - Após autenticar o usuário, resolver tenant/filial/terminal e emitir tokens JWT.

- **Sugestão de payload (extra)**:
  - `tenant_id`
  - `filial_id`
  - `terminal_id`
  - `user_id`
  - `request_id`
  - `perfil` (ex.: `"ADMIN"`, `"OPERADOR"`)

---

**`auth_login_falha`**

- **Descrição**:
  Falha no login por credenciais inválidas, usuário sem acesso à filial/terminal, tenant inativo, etc.

- **Momento do log**:
  - Antes de retornar resposta de erro HTTP.

- **Sugestão de payload (extra)**:
  - `tenant_id` (se derivado do contexto)
  - `filial_id` / `terminal_id` (se enviados na requisição)
  - `username` (mascarado se necessário)
  - `motivo` (ex.: `CREDENCIAIS_INVALIDAS`, `SEM_ACESSO_FILIAL`, `TENANT_INATIVO`)
  - `request_id`

---

### 4.2. Refresh de Token

**`auth_refresh_sucesso`**

- **Descrição**:
  Refresh de token JWT realizado com sucesso.

**`auth_refresh_falha`**

- **Descrição**:
  Refresh inválido (token expirado, blacklisted, malformado, etc.).

Ambos devem logar, no mínimo:

- `tenant_id`, `user_id`, `request_id`, `motivo` (no caso de falha).

---

## 5. Eventos — Multi-tenant

**`tenant_context_loaded`**

- **Descrição**:
  Contexto de tenant resolvido com sucesso a partir do header `X-Tenant-ID` ou equivalente.

- **Sugestão de payload (extra)**:
  - `tenant_id`
  - `schema_name`
  - `request_id`

---

**`tenant_inactive_access_blocked`**

- **Descrição**:
  Acesso bloqueado porque o tenant está inativo.

- **Sugestão de payload (extra)**:
  - `tenant_id`
  - `schema_name`
  - `request_id`
  - `motivo` (ex.: `TENANT_INATIVO`)

---

**`tenant_schema_mismatch_warning`** (opcional)

- **Descrição**:
  Situações em que o schema ativo não corresponde ao tenant esperado.

- Utilizado para detectar problemas de roteamento multi-tenant.

---

## 6. Eventos — Infra / Healthchecks

**`health_liveness_check`**

- **Descrição**:
  Verificação de que o processo está vivo (endpoint de liveness).

- Geralmente pode ser logado em `DEBUG` ou nem logado em produção para evitar ruído.

---

**`health_readiness_check`**

- **Descrição**:
  Verificação de que o backend está pronto para atender (conexão com banco, migrações ok, etc.).

- Quando algum problema é detectado, deve ser logado em `WARNING` ou `ERROR`, com:
  - `motivo`
  - `exception` (se houver)
  - `database_status`

---

## 7. Eventos — Outros Domínios

Conforme novos módulos forem sendo implementados (ex.: **vendas**, **caixa**, **estoque**), novos eventos devem ser adicionados ao logbook com as mesmas regras:

- Nome de evento claro, em lower_snake_case.
- Contexto completo (tenant, filial, terminal, user, request).
- Definição explícita se gera apenas log JSON ou também auditoria em banco.

Exemplos futuros:

- `caixa_abertura_sucesso`
- `caixa_fechamento_sucesso`
- `caixa_fechamento_divergencia`
- `estoque_movimentacao_registrada`

---

## 8. Relação com Auditoria em Banco

Eventos que **devem** gerar registro em tabela de auditoria:

- `nfce_emissao_sefaz_sucesso`
- `nfce_emissao_sefaz_rejeitada` (dependendo da regra de negócio)
- `nfce_cancelamento_sucesso`
- `nfce_inutilizacao_sucesso`
- Outros eventos fiscais críticos definidos em `auditoria_nfce.md`.

Regra geral:

- Toda operação fiscal que impacte **documentos oficiais** (emissão, cancelamento, inutilização) deve ter:
  - Log JSON com `event` bem definido.
  - Auditoria persistente em banco de dados, com ligação ao mesmo `request_id`.

---

## 9. Evolução do Logbook

- Qualquer novo evento de negócio **deve** ser incluído neste documento.
- Eventos existentes **não devem ser renomeados** sem migração/coordenação, para não quebrar:
  - Dashboards de observabilidade.
  - Regras de alerta.
  - Pipelines de auditoria.

Atualizações neste logbook devem ser feitas em conjunto com:

- `padroes_logs_backend.md` (formato/obrigatoriedade dos campos).
- `auditoria_nfce.md` (quando envolver eventos fiscais).
