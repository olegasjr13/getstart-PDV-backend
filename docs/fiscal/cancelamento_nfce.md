# Cancelamento de NFC-e — GetStart PDV (Modelo 65 / Layout 4.00)

## 1. Objetivo

Este documento define o **fluxo oficial de cancelamento de NFC-e** no GetStart PDV, considerando:

- NFC-e **Modelo 65**, layout **4.00** (padrão nacional).
- Arquitetura multi-tenant com filiais por UF (SP, MG, RJ, ES).
- Clients SEFAZ por UF (`SefazClientSP`, `SefazClientMG`, etc.).
- Auditoria obrigatória.
- Logs padronizados.
- Integração com o app PDV.
- Compatibilidade com POS Controle.

---

# 2. Conceitos Gerais

### 2.1. Quando pode cancelar uma NFC-e?

Cancelamento de NFC-e só é permitido quando:

- A NFC-e foi **autorizada** pela SEFAZ (tem chave/protocolo válidos).
- Está **dentro do prazo legal de cancelamento** da UF.
- Não foi emitido **evento de inutilização** que conflite com a numeração.
- Não houve cancelamento prévio da mesma chave (idempotência).

### 2.2. Prazo de Cancelamento (visão geral)

Cada UF define prazos específicos. No MVP:

- Seguir o **prazo padrão configurável** por UF (parametrização).
- O backend não codificará prazo fixo hard-coded, mas sim:
  - Campo de configuração na `Filial` ou tabela de parâmetros fiscais por UF.
  - Exemplo: `prazo_cancelamento_horas`.

Caso o prazo seja excedido:

- A SEFAZ rejeitará o evento de cancelamento.
- O sistema deve retornar erro apropriado (`FISCAL_400x`) e registrar auditoria.

---

# 3. Fluxo de Cancelamento (Visão Geral)

Fluxo padrão:

```
[1] Operador solicita cancelamento no PDV
[2] Backend valida parâmetros (filial, terminal, usuário, chave)
[3] Backend carrega NFC-e autorizada (documento fiscal)
[4] Backend valida prazo e regras fiscais
[5] Backend monta XML de evento de cancelamento (modelo 65, layout 4.00)
[6] Backend assina XML com certificado A1 da filial
[7] Client SEFAZ envia XML de cancelamento
[8] Backend trata resposta (autorizado/rejeitado/erro)
[9] Backend grava auditoria do evento
[10] Backend atualiza estado da NFC-e (cancelada)
[11] Logs são gerados conforme logbook
```

---

# 4. Requisitos de Entrada

### 4.1. Parâmetros mínimos no request do PDV

- `tenant_id` (via `X-Tenant-ID`)
- `filial_id`
- `terminal_id`
- `chave` da NFC-e a cancelar **ou** (`numero`, `serie`)
- `motivo` do cancelamento (texto obrigatório, dentro dos limites da legislação)
- `usuario` autenticado (via JWT)

### 4.2. Restrições

- Usuário deve ter permissão para **cancelar documentos**.
- Terminal deve estar ativo.
- Filial deve estar ativa e com ambiente (`mock` / `homolog` / `producao`) definido.
- Certificado A1 deve estar válido.

---

# 5. Modelo de Dados Envolvidos

Entidades envolvidas no cancelamento:

- `NfceDocumento`
  - Contém a NFC-e autorizada.
  - Campos: `chave`, `protocolo`, `numero`, `serie`, `status`, etc.
- `NfceCancelamento` (sugestão de entidade)
  - Registra o evento de cancelamento localmente.
- `NfceAuditoria`
  - Registra auditoria do evento (ver `auditoria_nfce.md`).

---

# 6. XML de Cancelamento — Modelo 65 / Layout 4.00

### 6.1. Estrutura Geral

O cancelamento é realizado via **Evento de NF-e** com:

- `tpEvento = 110111` (Cancelamento de NF-e)
- `mod = 65` (NFC-e)
- `versão = 4.00` do layout

O backend deve montar o XML de evento com as tags padrão do layout 4.00, incluindo:

- `<evento>`  
- `<infEvento>`  
- `<detEvento>`  

Campos relevantes:

- `chNFe` → chave da NFC-e a cancelar.
- `nProt` → protocolo de autorização da NFC-e.
- `xJust` → motivo do cancelamento (texto obrigatório, com limite mínimo/máximo definido pela SEFAZ).

### 6.2. Assinatura do XML

- O XML de evento deve ser assinado com o **certificado A1** da filial emissora.
- O processo de assinatura é responsabilidade do `BaseSefazClient` / camada fiscal.
- O app PDV não participa da assinatura.

---

# 7. Integração com Clients SEFAZ

O cancelamento deve ser implementado como um novo método no contrato dos clients:

```python
class SefazClientProtocol(Protocol):
    def emitir_nfce(self, *, pre_emissao: NfcePreEmissao) -> dict:
        ...

    def cancelar_nfce(self, *, documento: NfceDocumento, motivo: str) -> dict:
        ...
```

### 7.1. Entrada

- `documento`: instância de `NfceDocumento` já autorizada.
- `motivo`: texto do motivo de cancelamento.

### 7.2. Saída padronizada

Todos os clients devem retornar um `dict`:

```python
{
    "status": "CANCELADA" | "REJEITADA" | "ERRO",
    "codigo": "<codigo_retorno_sefaz_ou_mock>",
    "mensagem": "<mensagem_legivel>",
    "protocolo": "<protocolo_cancelamento_ou_none>",
    "xml_enviado": "<xml_evento_assinado>",
    "xml_resposta": "<xml_resposta_sefaz_ou_vazio>",
    "raw": { ... }
}
```

- Para ambiente `mock`, o comportamento é simulado.
- Para `homolog` e `producao`, o XML segue layout oficial 4.00.

---

# 8. Regras de Negócio no Cancelamento

### 8.1. Antes de enviar para SEFAZ

O backend deve validar:

1. **Estado da NFC-e**
   - Deve estar `AUTORIZADA`.
   - Não pode já estar `CANCELADA`.

2. **Prazo**
   - Verificar se está dentro do `prazo_cancelamento_horas` configurado para a UF/filial.
   - Se fora do prazo → retornar erro de negócio (`FISCAL_400x`) sem chamar SEFAZ.

3. **Ambiente**
   - Somente `homolog` e `producao` realizam cancelamento real.
   - `mock` simula o cancelamento sem SEFAZ.

4. **Motivo**
   - Obrigatório.
   - Tamanho mínimo/máximo conforme regras da SEFAZ (por exemplo, mínimo 15 caracteres).

### 8.2. Após retorno SEFAZ

- Se `status = CANCELADA`:
  - Atualizar `NfceDocumento.status` para `CANCELADA`.
  - Registrar `NfceCancelamento`.
  - Registrar auditoria (`NfceAuditoria`).
  - Gerar log `nfce_cancelamento_sucesso`.

- Se `status = REJEITADA`:
  - Não alterar status da NFC-e (continua autorizada).
  - Registrar auditoria com o motivo da rejeição.
  - Gerar log `nfce_cancelamento_falha`.
  - Retornar erro mapeado para a API (`FISCAL_400x`).

- Se `status = ERRO`:
  - Tratar como erro técnico (problema de comunicação, timeout, etc.).
  - Gerar log `nfce_cancelamento_falha`.
  - Retornar erro `FISCAL_500x`.

---

# 9. Idempotência do Cancelamento

Para evitar cancelamentos duplicados ou inconsistências:

### 9.1. Regra principal

- Cancelamento deve ser **idempotente por chave da NFC-e**.
- Se o backend receber pedido de cancelamento de uma NFC-e já cancelada:
  - Pode retornar sucesso “idempotente”, informando que já está cancelada.
  - Ou retornar erro específico de “já cancelada”, dependendo da política da aplicação.

### 9.2. Implementação sugerida

- Antes de tentar cancelar:
  - Verificar se já existe um `NfceCancelamento` com status de sucesso.
  - Verificar se a SEFAZ já possui um evento de cancelamento registrado para aquela chave (quando aplicável).

---

# 10. Auditoria de Cancelamento

Cada tentativa de cancelamento deve ser registrada na tabela de auditoria:

- `tipo_evento = "CANCELAMENTO"`
- Campos obrigatórios:
  - `tenant_id`
  - `schema_name`
  - `filial_id`
  - `terminal_id`
  - `numero`
  - `serie`
  - `chave`
  - `codigo` (retorno SEFAZ)
  - `mensagem`
  - `protocolo` (se cancelamento autorizado)
  - `xml_enviado`
  - `xml_resposta`
  - `ambiente`
  - `uf`
  - `request_id`
  - `user_id`

Ver documento `auditoria_nfce.md` para detalhes do modelo.

---

# 11. Logs de Cancelamento

Eventos no logbook:

- `nfce_cancelamento_sucesso`
- `nfce_cancelamento_falha`

### 11.1. `nfce_cancelamento_sucesso`

- Emitido quando a SEFAZ autoriza o evento de cancelamento.
- Campos recomendados:
  - `tenant_id`
  - `filial_id`
  - `terminal_id`
  - `user_id`
  - `request_id`
  - `chave`
  - `numero`
  - `serie`
  - `protocolo`
  - `ambiente`

### 11.2. `nfce_cancelamento_falha`

- Emitido em:
  - Rejeição SEFAZ
  - Erro técnico
- Incluir:
  - `codigo`
  - `mensagem`
  - `chave`
  - Tipo de erro (`NEGOCIO`, `SEFAZ`, `INFRA`)

---

# 12. Integração com o App PDV

### 12.1. Requisição

O app deve enviar algo como:

```json
POST /api/fiscal/nfce/cancelar/

{
  "filial_id": "...",
  "terminal_id": "...",
  "chave": "3519...<44 digitos>",
  "motivo": "Cliente desistiu da compra."
}
```

Com header:

- `Authorization: Bearer <token>`
- `X-Tenant-ID: <cnpj_raiz>`

### 12.2. Respostas

#### Sucesso (cancelamento autorizado)

```json
{
  "status": "CANCELADA",
  "message": "NFC-e cancelada com sucesso.",
  "chave": "3519...",
  "protocolo": "1234567890",
  "data_evento": "2025-01-01T12:00:00Z"
}
```

#### Rejeição SEFAZ

```json
{
  "error": "FISCAL_400x",
  "message": "Rejeitada pelo SEFAZ: Código 217 - NFC-e não encontrada.",
  "request_id": "..."
}
```

#### Erro técnico

```json
{
  "error": "FISCAL_500x",
  "message": "Erro ao comunicar com a SEFAZ para cancelamento.",
  "request_id": "..."
}
```

---

# 13. Ambiente MOCK

Em `nfce_ambiente = "mock"`:

- O cancelamento será simulado pelo `SefazClientMock`.
- Regras:
  - `status = CANCELADA` por padrão.
  - Permitir simular falhas via flags no payload (opcional).
- Auditoria:
  - Dev → opcional.
  - QA → recomendado.

---

# 14. Restrições Fiscais Importantes

- Cancelamento sempre gera **novo evento** SEFAZ vinculado à chave original.
- Não é possível cancelar NFC-e **denegada ou rejeitada** (somente autorizada).
- Prazo e condições podem variar por UF → devem ser parametrizáveis.
- Regras locais (ex.: caixa fechado, conciliação financeira) podem proibir cancelamento mesmo dentro do prazo fiscal.

---

# 15. Conclusão

O cancelamento de NFC-e no GetStart PDV segue:

- Padrão nacional (Modelo 65, layout 4.00).
- Arquitetura por clients SEFAZ por UF.
- Auditoria obrigatória.
- Logs alinhados ao logbook.
- Idempotência por chave.
- Integração clara com o app PDV.

Este documento deve ser seguido para implementar e testar o fluxo de cancelamento, bem como para suporte e auditoria.
