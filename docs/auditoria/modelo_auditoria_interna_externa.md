
---

## 5️⃣ `auditoria/modelo_auditoria_interna_externa.md` — Modelo de Auditoria

```markdown
# Modelo de Auditoria Interna e Externa — GetStart PDV

## 1. Objetivo

Definir quais evidências e trilhas o sistema deve fornecer para:

- **Auditoria fiscal** (NFC-e).
- **Auditoria operacional** (caixa, vendas).
- **Auditoria de segurança** (acessos, permissões).

---

## 2. Escopos de Auditoria

### 2.1 Fiscal

- Emissão e cancelamento de NFC-e.
- Numeração sequencial por série e terminal.
- Consistência de valores.

### 2.2 Operacional

- Abertura e fechamento de caixa.
- Movimentações (venda, suprimento, sangria, estorno).
- Reimpressões de DANFE.

### 2.3 Segurança

- Acessos de usuários (logins, logouts).
- Alterações em perfis e permissões.
- Acessos administrativos (ex.: painel de gestão).

---

## 3. Trilhas de Auditoria — Mínimo Exigido

### 3.1 NFC-e

Para cada NFC-e, deve ser possível saber:

- `tenant_id`
- `filial_id`
- `terminal_id`
- `numero`, `serie`
- `chave`
- `status` (`AUTORIZADA`, `CANCELADA`, etc.)
- Datas:
  - Criação da reserva.
  - Pré-emissão.
  - Emissão.
  - Cancelamento (se houver).
- Usuários envolvidos:
  - Usuário que realizou a venda.
  - Usuário que cancelou (se diferente).
- Eventos de log associados:
  - `nfce_reserva_numero`
  - `nfce_pre_emissao`
  - `nfce_emissao`
  - `nfce_cancelamento`
  - `nfce_fiscal_error` (se houver).

---

### 3.2 Caixa

Para cada sessão de caixa:

- `sessao_id`
- `user_id` responsável pela abertura.
- Data/hora de abertura e fechamento.
- Valores:
  - Saldo inicial.
  - Total de vendas.
  - Total de estornos.
  - Total de sangrias.
  - Total de suprimentos.
  - Saldo final.
- Divergências (diferença entre contagem do operador e cálculo do sistema).

---

### 3.3 Usuários e Acessos

Para auditoria de segurança, deve ser possível:

- Listar todos logins de um usuário em um período.
- Ver:
  - De quais IPs acessou.
  - Em quais tenants/filiais operou.
  - Quais ações críticas executou (ex.: cancelamento de NFC-e).

---

## 4. Fontes de Evidência

As principais fontes de evidência para auditoria são:

- Banco de dados:
  - Tabelas de:
    - NFC-e (reserva, pré-emissão, documento).
    - Caixa (sessão, movimentos).
    - Usuários, perfis, permissões.
- Logs:
  - LogBook (`observabilidade/logbook_eventos.md`).
  - Logs de aplicação (INFO, WARN, ERROR).
- Documentos:
  - XML de NFC-e (mock/real).
  - Arquivos de auditoria fiscal (`fiscal/auditoria_fiscal.docx`).

---

## 5. Relatórios de Auditoria

### 5.1 Relatório Fiscal

Conteúdo mínimo:

- Listagem de NFC-e por período:
  - Número, série, chave.
  - Status.
  - Valores.
- Cancelamentos:
  - Justificativa.
  - Usuário.
  - Data/hora.
- Divergências:
  - Ex.: notas canceladas sem estorno financeiro (devem ser bloqueadas pela regra `FISCAL_4020`, mas auditor pode verificar).

### 5.2 Relatório de Caixa

- Sessões de caixa do período.
- Saldos de abertura e fechamento.
- Movimentos detalhados:
  - Por tipo (venda, suprimento, sangria).
- Diferenças em fechamento.

### 5.3 Relatório de Acesso

- Logins por usuário.
- Eventos de login falho.
- Acessos a módulos de administração.

---

## 6. Processo de Auditoria

### 6.1 Auditoria Interna

- Conduzida pelo time do cliente ou pela própria GetStart.
- Periodicidade recomendada:
  - Mensal (fiscal e caixa).
  - Trimestral (segurança).

### 6.2 Auditoria Externa

- Feita por:
  - Contadores.
  - Auditorias externas.
- Sistema deve facilitar:
  - Exportação de relatórios.
  - Entrega de logs filtrados.
  - Acesso temporário controlado a dados (se aplicável).

---

## 7. Checklist de Conformidade

- [ ] Trilhas de auditoria existentes para NFC-e.
- [ ] Trilhas de auditoria existentes para caixa.
- [ ] Logs de login e ações sensíveis ativos.
- [ ] Relatórios padronizados disponíveis (ou fáceis de gerar).
- [ ] Política de retenção e acesso a logs documentada.

---
