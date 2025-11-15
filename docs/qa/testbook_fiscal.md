# GetStart PDV — Test Book Fiscal (Cenários de QA)

## 1. Cenários de Numeração NFC-e

### Caso 1.1 — Reserva simples
- Pré-condições:
  - Filial com A1 válido.
  - Terminal configurado com série 1.
- Passos:
  1. Login como OPERADOR.
  2. Chamar /fiscal/nfce/reservar-numero com request_id R1.
- Resultado esperado:
  - Retorna número 1 para série 1 se for a primeira emissão.
  - Registro em NfceNumeroReserva criado.
  - Log com event = nfce_reserva_numero.

### Caso 1.2 — Idempotência por request_id
- Pré-condições:
  - Mesmo cenário do Caso 1.1.
- Passos:
  1. Chamar /reservar-numero com o mesmo request_id R1.
- Resultado esperado:
  - Retorna o mesmo número anterior.
  - Nenhum novo registro em NfceNumeroReserva.
  - Log indica reutilização de reserva.

### Caso 1.3 — Concorrência (2 reservas em paralelo)
- Pré-condições:
  - A1 válido, terminal com série 1.
- Passos:
  1. Disparar 2 requisições quase simultâneas com request_ids diferentes (R2 e R3).
- Resultado esperado:
  - Um recebe numero 2 e outro 3 (ordem não garantida, mas sem duplicidade).
  - Não há erro de integridade.
  - NfceNumeroReserva possui numeros 1,2,3 únicos.

---

## 2. Cenários de Pré-Emissão

### Caso 2.1 — Pré-emissão válida
- Pré-condições:
  - Reserva obtida (numero 10, request_id RX).
- Passos:
  1. Chamar /pre-emissao com request_id RX e payload completo.
- Resultado esperado:
  - Registro em NfcePreEmissao criado.
  - Payload salvo integralmente.
  - Log nfce_pre_emissao gravado.

### Caso 2.2 — Pré-emissão com A1 expirado
- Pré-condições:
  - A1 expirado na Filial.
- Passos:
  1. Chamar /pre-emissao com request_id qualquer.
- Resultado esperado:
  - Resposta de erro com code FISCAL_4005.
  - Nenhum registro em NfcePreEmissao.

---

## 3. Cenários de Emissão

### Caso 3.1 — Emissão Mock com sucesso
- Pré-condições:
  - Pré-emissão existente para request_id RY.
- Passos:
  1. Chamar /emissao com o request_id RY.
- Resultado esperado:
  - XML retornado (mock).
  - DANFE em base64 retornado.
  - Status 'AUTORIZADA' armazenado em modelo de NFC-e.
  - Log nfce_emissao criado.

### Caso 3.2 — Emissão com pré-emissão inexistente
- Passos:
  1. Chamar /emissao com request_id inexistente.
- Resultado esperado:
  - Erro com code FISCAL_4010 (pré-emissão não encontrada).
  - Nenhum documento novo criado.

---

## 4. Cenários de Cancelamento

### Caso 4.1 — Cancelamento válido com estorno
- Pré-condições:
  - NFC-e emitida.
  - Estorno financeiro registrado em CaixaMovimento.
- Passos:
  1. Chamar /cancelar com chave e justificativa.
- Resultado esperado:
  - Status da NFC-e alterado para CANCELADA.
  - Protocolo de cancelamento gerado (mock).
  - Log nfce_cancelamento criado.

### Caso 4.2 — Cancelamento sem estorno
- Pré-condições:
  - NFC-e emitida sem estorno financeiro.
- Passos:
  1. Chamar /cancelar com chave.
- Resultado esperado:
  - Erro com code FISCAL_4020 (estorno obrigatório antes de cancelar).
  - NFC-e permanece AUTORIZADA.

---

## 5. Cenários Offline (Outbox)

### Caso 5.1 — Envio de eventos novos
- Pré-condições:
  - Lista de eventos offline com local_tx_uuid únicos.
- Passos:
  1. Chamar /sync/outbox com 10 eventos.
- Resultado esperado:
  - Todos inseridos em sync_evento como PENDENTE/PROCESSADO.
  - Resposta indica sucesso para todos.

### Caso 5.2 — Reenvio de eventos (dedupe)
- Pré-condições:
  - Mesmos eventos do Caso 5.1 reenviados.
- Passos:
  1. Chamar /sync/outbox com os mesmos local_tx_uuid.
- Resultado esperado:
  - Nenhum novo registro em sync_evento.
  - Resposta indica que foram ignorados como duplicados.

---

## 6. Cenários de Segurança

### Caso 6.1 — Acesso sem Authorization
- Passos:
  1. Chamar /fiscal/nfce/reservar-numero sem header Authorization.
- Resultado esperado:
  - 401 Unauthorized.

### Caso 6.2 — Acesso sem X-Tenant-ID
- Passos:
  1. Chamar /fiscal/nfce/reservar-numero sem header X-Tenant-ID.
- Resultado esperado:
  - 400/422 com código AUTH_1001 (tenant obrigatório).
