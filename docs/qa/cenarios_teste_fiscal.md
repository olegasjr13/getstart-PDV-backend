# Cenários de Teste Fiscal — GetStart PDV (NFC-e Modelo 65 / Layout 4.00)

## 1. Objetivo

Este documento define os **cenários oficiais de QA fiscal** para o GetStart PDV, cobrindo:

- Emissão NFC-e (normal, rejeitada, erro técnico)
- Cancelamento
- Inutilização
- Contingência (planejada)
- Regras tributárias (CFOP, NCM, CST/CSOSN, PIS/COFINS)
- Ambientes (mock, homolog, produção)
- Multi-tenant (vários CNPJs / filiais / terminais)

Ele serve como base para:

- Testes manuais
- Testes automatizados (unitários, de serviço, end-to-end)
- Checklists de regressão
- Cenários de homologação com clientes

---

## 2. Estrutura dos Cenários

Cada cenário deve ter:

- **ID**: código único (ex.: `NFCE-EMISSAO-001`)
- **Título**: descrição curta do objetivo
- **Pré-condições**
- **Passos**
- **Resultado esperado**
- **Ambiente**: `mock` | `homolog`
- **UF**: SP, MG, RJ, ES (quando aplicável)
- **Tags**: `fiscal`, `emissao`, `cancelamento`, etc.

---

## 3. Emissão NFC-e — Cenários Principais

### 3.1. Cenário `NFCE-EMISSAO-001`
**Título:** Emissão NFC-e simples — venda à vista, 1 item, consumidor não identificado

- **Ambiente:** `mock` (primeiro), depois `homolog`
- **UF:** SP
- **Pré-condições:**
  - Filial SP ativa com `nfce_ambiente = "homolog"` (para fase real).
  - CFOP, NCM, CST/CSOSN configurados.
  - Certificado A1 válido (para `homolog`).
- **Passos:**
  1. Logar no app PDV com usuário `OPERADOR`.
  2. Iniciar venda com 1 item (produto padrão, NCM válido, sem desconto).
  3. Informar pagamento em DINHEIRO, valor exato.
  4. Enviar pré-emissão para o backend.
  5. Solicitar emissão NFC-e.
- **Resultado esperado:**
  - `status = "AUTORIZADA"`.
  - Chave de acesso válida (44 dígitos).
  - Documento registrado em `NfceDocumento`.
  - Auditoria em `NfceAuditoria` com `tipo_evento = "EMISSAO_AUTORIZADA"`.
  - Log `nfce_emissao_sefaz_sucesso` para `homolog`.

---

### 3.2. Cenário `NFCE-EMISSAO-002`
**Título:** Emissão NFC-e com CPF do consumidor

- **Ambiente:** `homolog`
- **UF:** SP
- **Pré-condições:**
  - Mesmo que `NFCE-EMISSAO-001`.
- **Passos:**
  1. Iniciar venda com 1 item.
  2. Informar CPF do consumidor.
  3. Realizar pagamento (cartão, por exemplo).
  4. Emitir NFC-e.
- **Resultado esperado:**
  - NFC-e autorizada, `<dest>` preenchido com `<CPF>`.
  - XML gravado na auditoria.
  - Chave e protocolo válidos.

---

### 3.3. Cenário `NFCE-EMISSAO-003`
**Título:** Emissão com múltiplos itens e múltiplas formas de pagamento

- **Ambiente:** `homolog`
- **UF:** SP
- **Pré-condições:**
  - Produtos com NCM e alíquotas válidas.
- **Passos:**
  1. Adicionar 3 itens distintos.
  2. Usar 2 tipos de pagamento: DINHEIRO + CARTÃO.
  3. Emitir NFC-e.
- **Resultado esperado:**
  - `<det>` para cada item com `NCM`, `CFOP`, `CST/CSOSN`.
  - `<pag>` com múltiplos `<detPag>`.
  - Totais (`<ICMSTot>`) consistentes.

---

### 3.4. Cenário `NFCE-EMISSAO-004`
**Título:** Emissão com produto sem NCM configurado (erro de validação interna)

- **Ambiente:** `mock` / `homolog`
- **UF:** qualquer
- **Passos:**
  1. Criar produto sem NCM (ou desativar o NCM).
  2. Tentar emitir NFC-e com esse produto.
- **Resultado esperado:**
  - Backend recusa antes de chamar SEFAZ.
  - Retorno HTTP 400 com `error = "FISCAL_4007"` (por exemplo).
  - Mensagem clara: “Produto sem NCM configurado”.
  - Nenhuma tentativa de comunicação com SEFAZ.

---

### 3.5. Cenário `NFCE-EMISSAO-005`
**Título:** Emissão com certificado A1 vencido

- **Ambiente:** `homolog`
- **Pré-condições:**
  - Filial com certificado A1 configurado, porém expirado.
- **Passos:**
  1. Tentar emitir NFC-e.
- **Resultado esperado:**
  - Backend bloqueia emissão.
  - Erro `FISCAL_4002` (certificado inválido ou vencido).
  - Log detalhado (sem expor senha).

---

## 4. Emissão NFC-e — Cenários por Regime Tributário

### 4.1. Cenário `NFCE-TRIB-001`
**Título:** Emissão – Simples Nacional – CSOSN 102

- **Pré-condições:**
  - Filial com `CRT = 1` (Simples Nacional).
  - Produto configurado com CSOSN 102.
- **Resultado esperado:**
  - XML `<ICMSSN102>` com `CSOSN=102`.
  - Sem destaque de ICMS.

---

### 4.2. Cenário `NFCE-TRIB-002`
**Título:** Emissão – Regime Normal – ICMS00

- **Pré-condições:**
  - Filial com `CRT = 3`.
  - Produto com CST 00 e alíquota configurada.
- **Resultado esperado:**
  - `<ICMS00>` com `vBC`, `pICMS`, `vICMS` corretos.
  - Totais de `vICMS` e `vBC` batendo com somatório dos itens.

---

## 5. Cancelamento NFC-e — Cenários

### 5.1. Cenário `NFCE-CANC-001`
**Título:** Cancelamento dentro do prazo — sucesso

- **Pré-condições:**
  - NFC-e autorizada em `homolog`.
  - Dentro do prazo de cancelamento.
- **Passos:**
  1. Enviar requisição de cancelamento com `chave` + `motivo`.
- **Resultado esperado:**
  - Evento de cancelamento autorizado.
  - `NfceDocumento.status = "CANCELADA"`.
  - Auditoria com `tipo_evento = "CANCELAMENTO"`.
  - Log `nfce_cancelamento_sucesso`.

---

### 5.2. Cenário `NFCE-CANC-002`
**Título:** Cancelamento fora do prazo — rejeição

- **Pré-condições:**
  - NFC-e autorizada com data/hora ajustadas para ultrapassar o prazo simulado.
- **Passos:**
  1. Tentar cancelar a NFC-e.
- **Resultado esperado:**
  - Rejeição SEFAZ com código de prazo expirado.
  - API devolve `error = "FISCAL_400x"`.
  - Auditoria registra rejeição.
  - `NfceDocumento` permanece autorizada.

---

### 5.3. Cenário `NFCE-CANC-003`
**Título:** Cancelamento de NFC-e já cancelada (idempotência)

- **Pré-condições:**
  - NFC-e já cancelada.
- **Passos:**
  1. Tentar cancelar novamente.
- **Resultado esperado (política interna):**
  - API retorna mensagem indicando que a NFC-e já está cancelada.
  - Nenhuma nova chamada à SEFAZ.
  - Auditoria não duplica evento.

---

## 6. Inutilização de Numeração — Cenários

### 6.1. Cenário `NFCE-INUT-001`
**Título:** Inutilização de faixa livre — sucesso

- **Pré-condições:**
  - Série e faixa (ex.: 151–160) ainda não usadas.
- **Passos:**
  1. Realizar POST `/api/fiscal/nfce/inutilizar/` com serie, faixa e motivo.
- **Resultado esperado:**
  - Retorno `status = "INUTILIZADA"`.
  - Registro em `NfceInutilizacao`.
  - Auditoria com `tipo_evento = "INUTILIZACAO"`.
  - Log `nfce_inutilizacao_sucesso`.

---

### 6.2. Cenário `NFCE-INUT-002`
**Título:** Inutilização com número já autorizado na faixa — rejeição

- **Pré-condições:**
  - Número 155 já utilizado em NFC-e autorizada.
- **Passos:**
  1. Pedir inutilização da faixa 151–160.
- **Resultado esperado:**
  - Backend detecta número usado.
  - Retorno `error = "FISCAL_400x"`.
  - Nenhuma chamada à SEFAZ ou, se chamar, rejeição 563.
  - Auditoria registra tentativa e resultado.

---

### 6.3. Cenário `NFCE-INUT-003`
**Título:** Inutilização idempotente — mesma faixa 2x

- **Pré-condições:**
  - Inutilização da faixa 151–160 já feita.
- **Passos:**
  1. Reenviar a mesma solicitação de inutilização.
- **Resultado esperado:**
  - Backend reconhece que já existe inutilização para a faixa.
  - Retorna resultado idempotente (sem novo envio à SEFAZ).

---

## 7. Contingência — Cenários (Planejados)

### 7.1. Cenário `NFCE-CONT-001`
**Título:** Timeout SEFAZ → ativação EPEC (planejado)

- **Ambiente:** simulado em `mock`.
- **Passos:**
  1. Forçar timeout no client SEFAZ (mock).
  2. Verificar se backend indica `modo_contingencia = "epec"`.
- **Resultado esperado:**
  - API retorna opção de contingência.
  - PDV registra estado de contingência.

---

### 7.2. Cenário `NFCE-CONT-002`
**Título:** Reconciliação pós-contingência (planejado)

- **Pré-condições:**
  - Vendas marcadas como “pendentes de envio” (EPEC ou offline).
- **Resultado esperado (futuro):**
  - Backend reenvia NFC-e.
  - Auditoria registra evento normal.

---

## 8. Multi-Tenant e Multi-UF — Cenários

### 8.1. Cenário `NFCE-MULTI-001`
**Título:** Emissão em tenants distintos (CNPJ A e CNPJ B)

- **Pré-condições:**
  - Dois tenants distintos, cada um com sua filial.
- **Passos:**
  1. Emitir NFC-e no Tenant A.
  2. Emitir NFC-e no Tenant B.
- **Resultado esperado:**
  - Cada NFC-e gravada no schema correto.
  - Nenhum dado cruzado.
  - Auditores conseguem ver por tenant.

---

### 8.2. Cenário `NFCE-MULTI-002`
**Título:** Emissões em UFs diferentes (SP, MG, RJ, ES)

- **Passos:**
  1. Emitir NFC-e em cada UF.
- **Resultado esperado:**
  - `cUF`, `cMunFG`, `ICMS` e CFOPs condizentes por UF.
  - Nenhuma falha de validação de XML por schema/UF.

---

## 9. Erros Técnicos e Resiliência

### 9.1. Cenário `NFCE-ERR-001`
**Título:** Timeout SEFAZ (erro 500x) sem contingência habilitada

- **Passos:**
  1. Forçar timeout.
- **Resultado:**
  - Erro `FISCAL_5005`.
  - Mensagem amigável para o operador.
  - Nenhuma duplicidade de emissão.

---

### 9.2. Cenário `NFCE-ERR-002`
**Título:** Erro genérico interno do backend

- **Passos:**
  1. Forçar exceção no service de emissão (em ambiente de teste).
- **Resultado:**
  - Erro `INTERNAL_5000`.
  - Nenhum stack trace vazado na API.
  - Erro completo registrado em logs/Sentry.

---

## 10. Checklists de QA

### 10.1. Antes de rodar a suíte fiscal

- [ ] Filiais criadas para SP, MG, RJ, ES.  
- [ ] Certificados A1 configurados para ambiente `homolog`.  
- [ ] Produtos com NCM, CFOP, CST/CSOSN válidos.  
- [ ] Seeds CFOP/NCM aplicados.  
- [ ] Ambiente `mock` validado para testes rápidos.

### 10.2. Após rodar os testes

- [ ] Conferir `NfceDocumento` para ver numeração correta.  
- [ ] Conferir `NfceAuditoria` para todos os cenários.  
- [ ] Verificar logs de sucesso/erro para cada fluxo.  
- [ ] Verificar se não houve emissão duplicada.  

---

## 11. Conclusão

Este documento fornece um **conjunto mínimo robusto de cenários fiscais** para validação do GetStart PDV, alinhado:

- Aos documentos de regras fiscais, XML, cancelamento, inutilização e contingência.
- À arquitetura multi-tenant.
- Ao comportamento esperado em POS real.

Esses cenários devem ser evoluídos conforme novas UFs, regimes ou funcionalidades fiscais forem adicionados.
