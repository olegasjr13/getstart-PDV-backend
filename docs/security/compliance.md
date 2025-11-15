# Compliance, LGPD e Auditoria — GetStart PDV

## 1. Objetivo

Definir diretrizes de:

- **Privacidade e proteção de dados** (LGPD).
- **Retenção de dados e logs**.
- **Auditoria fiscal e operacional**.
- **Responsabilidades e papéis**.

Este documento é referência para:

- Backend / Infra.
- Jurídico/Compliance.
- Time Fiscal.
- Gestão de Produto.

---

## 2. Base legal e princípios (LGPD)

### 2.1 Princípios básicos

A plataforma deve seguir os princípios da LGPD:

- Finalidade → Dados coletados para fins legítimos e específicos.
- Adequação → Tratamento compatível com as finalidades informadas.
- Necessidade → Coletar e armazenar **apenas o necessário**.
- Transparência → Clientes (empresas) devem saber como os dados são tratados.
- Segurança → Medidas para proteger dados contra incidentes.
- Prevenção → Ações para reduzir riscos.
- Responsabilização → Evidenciar conformidade.

### 2.2 Dados pessoais envolvidos

Exemplos típicos no contexto PDV:

- Dados de **usuários do sistema** (operadores, supervisores, gerentes).
  - Nome, e-mail, CPF (se usado).
- Dados de **clientes finais** (consumidor da NFC-e).
  - CPF (quando informado).
  - Nome.
- Dados transacionais:
  - Valor da compra.
  - Meio de pagamento.
  - Itens adquiridos.

---

## 3. Classificação de dados

### 3.1 Categorias

- **Dados sensíveis** (alto risco):
  - Qualquer coisa ligada a meios de pagamento que possa identificar cartão (PAN completo, CVV) → **não deve ser armazenado**.
  - Senhas, PINs, tokens de acesso.
- **Dados pessoais**:
  - Nome, e-mail, CPF, telefone.
- **Dados fiscais**:
  - Chave NFC-e, XML, valores, CFOP, etc.
- **Dados técnicos**:
  - Logs de erro, métricas, IPs, user agents.

### 3.2 Tratamento diferenciado

- Dados sensíveis:
  - Não armazenar, ou armazenar de forma tokenizada/irreversível (ex.: hashes).
- Dados pessoais:
  - Proteger com controles de acesso adequados.
  - Permitir exclusão/anonimização sob demanda (onde aplicável e permitido por lei fiscal).
- Dados fiscais:
  - Normalmente exigem período mínimo de retenção por lei (ver com time contábil/fiscal).

---

## 4. Retenção e eliminação de dados

### 4.1 Retenção de dados de aplicação

- Dados fiscais (NFC-e):
  - Seguir legislação federal/estadual.
  - Exemplo: manter por 5 anos (validar oficialmente com fiscal).
- Dados de usuários internos:
  - Enquanto houver relação contratual com o cliente.
  - Ao inativar usuário, manter histórico de ações (para trilha de auditoria).
- Eventos de sync, logs técnicos, etc.:
  - Prazo menor (ex.: 90 dias - 12 meses, conforme categoria).

### 4.2 Retenção de logs

- Logs de aplicação:
  - Período sugerido: 90–180 dias (conforme custo/risco).
- Logs de auditoria fiscal:
  - Podem seguir a mesma regra dos documentos fiscais (5 anos), quando contêm evidências de emissão/cancelamento.

### 4.3 Eliminação e anonimização

- Ao excluir dados de um usuário ou cliente, considerar:
  - Obrigações legais (dados fiscais podem não poder ser excluídos).
  - Possibilidade de anonimizar (remover nome, guardar apenas identificação fiscal, quando permitido).

---

## 5. Auditoria

### 5.1 Auditoria fiscal

- Ver documento:
  - `fiscal/auditoria_fiscal.docx`
- Objetivo:
  - Ser capaz de reconstruir:
    - Quem emitiu/cancelou NFC-e.
    - Em qual data/hora.
    - Em qual terminal.
    - Com qual certificado e chave.

### 5.2 Auditoria de acesso

- Registrar:
  - Logins e logouts.
  - Alterações de perfis e permissões.
  - Acessos a módulos administrativos.
- Manter:
  - `user_id`, `tenant_id`, `filial_id`, `ip`, `user_agent`, `timestamp`.

### 5.3 Auditoria de alteração de dados críticos

- Ex.: ajustes em cadastros fiscais, produtos, alíquotas, parâmetros de NFC-e.
- Recomenda-se:
  - Tabelas de histórico (ex.: `*_history`).
  - Ou trilhas em tabela de auditoria específica.

---

## 6. Papéis e responsabilidades

### 6.1 Interno (plataforma GetStart PDV)

- **DPO / Encarregado**:
  - Responsável por privacidade de dados, comunicação com ANPD.
- **Time de Segurança**:
  - Responsável por hardening, pentests, monitoramento de incidentes.
- **Time de Produto**:
  - Garantir que novas features considerem privacidade por design.
- **Time de Engenharia**:
  - Implementar medidas de segurança e correções.

### 6.2 Clientes (empresas que usam o PDV)

- Responsáveis por:
  - Coletar consentimento de consumidores quando necessário.
  - Usar o sistema de forma adequada.
  - Configurar perfis e acessos de usuários corretamente.

---

## 7. Incidentes de segurança

### 7.1 Detecção

- Monitorar:
  - Erros incomuns (picos de 5xx).
  - Tentativas de login mal sucedidas em massa.
  - Acessos fora de padrão (horário/local incomum).

### 7.2 Resposta

Plano mínimo de resposta a incidentes:

1. Identificar e conter (ex.: bloquear contas, revogar tokens).
2. Analisar escopo:
   - Que dados foram potencialmente expostos?
3. Corrigir vulnerabilidade raiz.
4. Notificar partes afetadas quando exigido por lei.
5. Registrar o incidente:
   - Causa.
   - Impacto.
   - Ações tomadas.
   - Lições aprendidas.

---

## 8. Conformidade contínua

- Revisar estes documentos periodicamente (ex.: a cada 6–12 meses).
- Realizar:
  - Avaliações de vulnerabilidade.
  - Pentests periódicos em ambiente de homologação.
- Garantir que:
  - Mudanças arquiteturais relevantes **sempre** sejam refletidas:
    - Em `arquitetura/*`
    - Em `security/*`
    - Em `fiscal/*` (quando afetarem NFC-e).

---

## 9. Checklists de compliance

- [ ] Dados pessoais mapeados (quem coleta, onde armazena, por quê).
- [ ] Política de retenção de dados definida por tipo de dado.
- [ ] Logs de auditoria fiscal implementados.
- [ ] Logs de acesso administrativo armazenados e com acesso controlado.
- [ ] Procedimento de resposta a incidentes definido.
- [ ] Time conhece estes documentos e sabe onde encontrá-los.

---
