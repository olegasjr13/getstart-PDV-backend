# Regras Fiscais — GetStart PDV (Versão Enterprise)

## 1. Objetivo
Este documento consolida **todas as regras fiscais implementadas** no backend do GetStart PDV e define o padrão para evolução futura. Ele serve para:
- garantir conformidade fiscal,
- orientar backend, mobile e QA,
- orientar auditores internos/externos,
- centralizar regras de negócio do módulo NFC-e.

---

# 2. Escopo Fiscal

O sistema suporta o fluxo fiscal:
```
RESERVA → PRÉ-EMISSÃO → EMISSÃO (MOCK) → CANCELAMENTO (futuro)
```

Baseado nos serviços:
- `NfceNumeroService`
- `NfcePreEmissaoService`
- `NfceEmissaoService`
- Modelos `NfceReserva`, `NfcePreEmissao`, `NfceEmitida`
- Testes fiscais reais já existentes

---

# 3. Regras Gerais Obrigatórias

## 3.1 Idempotência
Toda operação fiscal deve ser idempotente por `request_id`.
- Mesmo request → mesmo resultado.
- Garante integridade fiscal em casos de falha de rede.

## 3.2 Multi-Tenant
Cada tenant possui:
- própria sequência numérica,
- seu próprio certificado (futuro),
- seu próprio ambiente fiscal.

Nunca compartilhar dados fiscais entre tenants.

## 3.3 Integridade Fiscal
Nenhuma NFC-e pode ser:
- sobrescrita,
- reaproveitada,
- alterada após emissão (exceto cancelamento).

---

# 4. Regras da Etapa RESERVA

## 4.1 Regras Implementadas
1. A combinação `(tenant, filial, terminal, serie)` define o contador fiscal.
2. Se o mesmo request_id for enviado:
   - retornar a mesma reserva.
3. Nunca pular número fiscal.
4. Terminal deve estar ATIVO.
5. Filial deve existir.
6. Tenant deve estar funcional.

## 4.2 Erros Associados
- `FISCAL_4001` – Terminal inválido
- `FISCAL_4002` – Solicitação duplicada inválida
- `FISCAL_4008` – Terminal inativo

---

# 5. Regras da PRÉ-EMISSÃO

## 5.1 Itens
- quantidade > 0
- valor_unitário > 0
- total_item = quantidade * valor
- impostos obrigatórios presentes no payload

## 5.2 Pagamentos
- valor ≥ 0
- forma de pagamento válida
- soma dos pagamentos = valor total da venda

## 5.3 Validação de Totais
```
valor_total_itens == valor_total_pagamentos == valor_total_principal
```

## 5.4 Reserva Obrigatória
Somente é permitido pré-emissão após reserva.

## 5.5 Erros
- `FISCAL_4003` – Divergência de totais
- `FISCAL_4004` – Item inválido
- `FISCAL_4005` – Pagamento inválido

---

# 6. Regras da EMISSÃO (MOCK)

## 6.1 XML MOCK
O XML mock deve:
- seguir estrutura oficial da NFC-e,
- conter chave realista,
- conter protocolo,
- usar ambiente homologação.

## 6.2 Chave
Gerada com:
- código UF (35 por padrão),
- CNPJ do tenant,
- série,
- número,
- código numérico.

## 6.3 Emissão Real (futuro)
Validações:
- CSC por UF,
- Certificado A1,
- Webservices:
  - autorizador SVRS,
  - consulta de status,
  - envio lote,
  - retorno lote.

## 6.4 Erros
- `FISCAL_4010` – Tentativa de emitir sem pré-emissão

---

# 7. Regras de CANCELAMENTO (versão futura)

## 7.1 Condições obrigatórias
- NFC-e emitida
- Dentro do prazo permitido pela UF
- Pagamentos estornados
- Terminal autorizado

## 7.2 Registro obrigatório
Evento `fiscal_cancelada`.

---

# 8. Regras por UF (futuro)

Estrutura:
```
UFRulesFactory.get(uf)
```

Cada UF pode definir:
- CFOP padrão,
- CSOSN,
- CST,
- exigências de QR Code,
- regras de contingência.

---

# 9. Tabela de Erros Fiscais Geral

| Código | Descrição |
|--------|-----------|
| FISCAL_4001 | Terminal inválido |
| FISCAL_4002 | Solicitação duplicada inválida |
| FISCAL_4003 | Divergência de totais |
| FISCAL_4004 | Item inválido |
| FISCAL_4005 | Pagamento inválido |
| FISCAL_4006 | Pré-emissão não encontrada |
| FISCAL_4007 | Reserva não encontrada |
| FISCAL_4008 | Terminal inativo |
| FISCAL_4010 | Emitir sem pré-emissão |

---

# 10. Conclusão

Este documento, alinhado ao código atual do projeto, formaliza todas as regras fiscais já implementadas e define o padrão para evolução futura, garantindo segurança jurídica e integridade das NFC-e.
