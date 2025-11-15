
---

## 3️⃣ `docs/qa/estrategia_qa.md`

```markdown
# Estratégia de QA — GetStart PDV Backend

Este documento define a estratégia de **Qualidade de Software (QA)** para o backend GetStart PDV, complementando o `testbook_fiscal.md`.

---

## 1. Objetivos de QA

- Garantir que os fluxos críticos (fiscal, caixa, sync) funcionem de forma:
  - Consistente.
  - Determinística.
  - Idempotente.
- Garantir que regressões sejam detectadas cedo.
- Viabilizar auditoria técnica e fiscal com confiança.

---

## 2. Tipos de Testes

### 2.1 Testes Unitários

- Escopo:
  - Funções puras.
  - Serviços internos (ex.: cálculo de próxima numeração, geração de chave NFC-e mock).
  - Validações de regras de negócio isoladas.
- Ferramentas:
  - `pytest` + `pytest-django`.
- Objetivo:
  - Cobrir cenários positivos/negativos por função.

### 2.2 Testes de Serviço (API)

- Escopo:
  - Endpoints REST expostos (ex.: `/fiscal/nfce/reservar-numero`).
- Ferramentas:
  - `pytest` com `APIClient` (DRF) ou `httpx`.
- Objetivo:
  - Validar contratos.
  - Verificar estrutura de responses, erros, autenticação e headers.

### 2.3 Testes de Integração

- Escopo:
  - Fluxo completo envolvendo múltiplos domínios:
    - Login → Reserva → Pré-emissão → Emissão.
    - Estorno → Cancelamento.
    - Sync offline.
- Ferramentas:
  - `pytest` em ambiente de teste com DB real (PostgreSQL ou SQLite configurado).
- Objetivo:
  - Garantir integração correta entre apps (`fiscal`, `caixa`, `pagamentos`, `sync`).

### 2.4 Testes de Carga e Concorrência (futuro)

- Escopo:
  - Reserva de numeração com múltiplos terminais.
  - Emissão simultânea em diferentes filiais.
- Ferramentas:
  - Locust, K6, ou JMeter.
- Objetivo:
  - Validar locking e transações na reserva.
  - Detectar problemas de desempenho / deadlock.

---

## 3. Cobertura Mínima Recomendada

- Testes unitários: **≥ 70%** das regras fiscais e serviços de domínio.
- Testes de serviço (API): testes automatizados para todos endpoints críticos:
  - `/auth/login`
  - `/fiscal/nfce/*`
  - `/sync/outbox`
- Casos de teste fiscais:
  - Todos os cenários listados em `testbook_fiscal.md` devem estar cobertos por pelo menos 1 teste automatizado.

---

## 4. Foco em Fluxos Críticos

### 4.1 Reserva de Numeração

- Cenários:
  - Primeira reserva do terminal/filial/série.
  - `request_id` repetido (idempotência).
  - Reservas em paralelo (concorrência).
- Verificações:
  - Sequência sem buracos.
  - Locks e transações funcionando.

### 4.2 Pré-Emissão

- Cenários:
  - Pré-emissão válida.
  - Sem reserva prévia.
  - A1 expirado.
  - Totais inconsistentes (sugerido em conjunto com validações futuras).

### 4.3 Emissão

- Cenários:
  - Emissão com pré-emissão existente.
  - Emissão sem pré-emissão.
  - Emissão repetida (idempotência).
- Verificações:
  - XML gerado.
  - Chave coerente com número/série.

### 4.4 Cancelamento

- Cenários:
  - Cancelamento com estorno.
  - Cancelamento sem estorno (FISCAL_4020).
  - Cancelamento de NFC-e já cancelada (erro esperado).
- Verificações:
  - Estados da NFC-e.
  - Vínculo com caixa/pagamentos.

### 4.5 Sync Offline

- Cenários:
  - Envio de vários eventos novos.
  - Reenvio dos mesmos eventos (`local_tx_uuid`).
- Verificações:
  - Idempotência.
  - Status dos eventos (PENDENTE → PROCESSADO/ERRO).

---

## 5. Ambientes de Teste

### 5.1 Ambiente Local

- Dev roda:
  - Docker Compose (DB + backend).
- Uso:
  - Desenvolvimento diário.
  - Execução rápida de testes unitários e de serviço.

### 5.2 Ambiente de Homologação

- Espelha o ambiente de produção:
  - NGINX + backend + DB.
- Uso:
  - Testes manuais com PDV real/simulador.
  - Testes integrados mais pesados.
- Dados:
  - Fixtures de tenants/filiais/terminais pré-cadastrados.

---

## 6. Automatização e Pipeline

### 6.1 CI

No repo de backend (e/ou infra):

- Etapas mínimas:

1. `lint` (flake8/ruff, isort, black — opcional).
2. `pytest` com:
   - testes unitários.
   - testes de serviço.
3. Geração de relatório de cobertura:
   - `coverage.xml`.

### 6.2 Gatilhos

- Pull Requests:
  - Execução obrigatória da suíte de testes.
  - Rejeitar merge se falhar testes ou cobertura abaixo do mínimo.
- Merge na main:
  - Pode disparar deploy para ambiente de homologação (CD).

---

## 7. Padronização de Testes

### 7.1 Organização de Arquivos

Sugestão:

- `tests/`
  - `test_auth/`
  - `test_fiscal/`
  - `test_caixa/`
  - `test_sync/`
  - `conftest.py` (fixtures comuns)

### 7.2 Estilo de Teste

- Nomes descritivos:
  - `test_reserva_numero_primeira_vez`
  - `test_reserva_numero_idempotente_request_id`
- Uso de fixtures:
  - Tenant, filial, terminal, usuário, sessão de caixa.
- Logs:
  - Em testes mais críticos, logar steps para facilitar diagnóstico.

---

## 8. Testes Manuais (Complementares)

Mesmo com automação, alguns testes manuais são recomendados:

- Fluxo completo com PDV real ou emulador:
  - Venda simples.
  - Cancelamento.
  - Perda de conexão + sync offline.
- Validação com contador/fiscal:
  - Revisão de XML mock.
  - Conferência de numeração.

