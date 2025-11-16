# Inutilização de Numeração de NFC-e — GetStart PDV (Modelo 65 / Layout 4.00)

## 1. Objetivo

Este documento descreve de forma **completa e padronizada** o processo de **inutilização de numeração NFC-e** no GetStart PDV, considerando:

- NFC-e **Modelo 65**, layout **4.00** (padrão nacional).
- Arquitetura multi-tenant (cada tenant = um schema).
- Emissão por UF: **SP, MG, RJ, ES**.
- Clients SEFAZ por UF.
- Logs e auditoria obrigatória.
- Idempotência por faixa inutilizada.
- Segurança e consistência numérica.
- Comportamento alinhado com POS Controle.

---

# 2. Entendimento da Inutilização

A **inutilização** é o processo fiscal de informar à SEFAZ que uma **faixa de numeração** não será utilizada.

Usado quando:

- A sequência fiscal tem falhas.
- A pré-emissão foi iniciada mas não houve emissão.
- O terminal ficou inconsistente.
- Numeração ficou reservada mas nunca emitida.
- Operações de rollback ou falhas operacionais criam “buracos”.

A inutilização **não cancela** NFC-e.  
Ela apenas formaliza que a **faixa entre `NInicial` e `NFinal` não será usada**.

---

# 3. Regras da SEFAZ (NFC-e 65 / Layout 4.00)

### 3.1. Evento da SEFAZ

A inutilização é enviada como **evento próprio**, não relacionado a um documento existente.

Parâmetros principais:

- `tpAmb` – ambiente (homologação/produção)
- `mod=65` – NFC-e
- `serie` – série da numeração
- `nNFIni` – número inicial
- `nNFFin` – número final
- `xJust` – justificativa (motivo obrigatório)
- `tpEvento=110` – padrão de inutilização (varia por UF conforme endpoints)

### 3.2. Restrição importante

A faixa **não pode incluir números já autorizados**.  
Se qualquer número no intervalo já foi emitido, SEFAZ retornará rejeição:

> *Rejeição 563 – Número da NFC-e já utilizado.*

### 3.3. Rejeições comuns

| Código | Significado |
|-------|-------------|
| **563** | Número já utilizado |
| **564** | Faixa inválida |
| **565** | Série inválida |
| **566** | Já existe inutilização para essa faixa |
| **567** | Faixa fora da sequência lógica |
| **568** | Inutilização fora do prazo |
| **999** | Erro inesperado |

---

# 4. Fluxo de Inutilização no GetStart PDV

O processo deve seguir:

```
[1] PDV solicita inutilização (motivo + faixa)
[2] Backend valida filial, terminal, permissão
[3] Backend valida faixa (nenhum número autorizado)
[4] Backend checa se já existe inutilização idêntica
[5] Backend monta XML de inutilização (modelo 65 / layout 4.00)
[6] Backend assina XML com A1
[7] Client SEFAZ envia inutilização
[8] Backend registra auditoria
[9] Backend salva registro NfceInutilizacao
[10] Backend retorna resposta ao PDV
```

---

# 5. Parâmetros esperados na requisição do PDV

```json
{
  "filial_id": "...",
  "terminal_id": "...",
  "serie": 1,
  "numero_inicial": 151,
  "numero_final": 160,
  "motivo": "Falha operacional no terminal."
}
```

Headers:

- `Authorization: Bearer <token>`
- `X-Tenant-ID: <cnpj_raiz>`

---

# 6. Validações do Backend (antes de chamar SEFAZ)

### 6.1. Validações de negócio

1. Série deve existir para a filial.
2. `numero_inicial <= numero_final`
3. O intervalo deve estar dentro do range permitido pela UF.
4. O terminal deve ser autorizado para a filial.
5. A filial deve estar ativa.
6. O usuário deve ter permissão para inutilização.
7. Justificativa é obrigatória (mín. 15 caracteres).

### 6.2. Validações fiscais **críticas**

Antes de enviar para SEFAZ:

- Confirmar que nenhum número da faixa:
  - Foi autorizado.
  - Foi cancelado.
  - Está com pré-emissão pendente.
  - Está reservado (`NfceNumeroReserva`) sem uso.

Se existir qualquer número comprometido → **erro de negócio** (`FISCAL_400x`).

### 6.3. Idempotência

Se já houver inutilização para:

- mesma série
- mesmo número inicial
- mesmo número final

→ deve retornar resultado **idempotente**, sem chamar SEFAZ novamente.

---

# 7. XML de Inutilização — Modelo 65 / Layout 4.00

Estrutura geral:

- `<inutNFe>`  
- `<infInut>`  
- `<xJust>`  

Campos essenciais:

- `mod=65`
- `serie`
- `nNFIni`
- `nNFFin`
- `xJust`
- `CNPJ` da filial
- `UF`
- `versao="4.00"`

O XML deve ser:

- Montado pelo `BaseSefazClient`.
- Assinado digitalmente com o A1.
- Validado contra XSD quando aplicável.

---

# 8. SefazClientProtocol — Adaptação

O contrato deve conter método para inutilização:

```python
class SefazClientProtocol(Protocol):
    def emitir_nfce(self, *, pre_emissao: NfcePreEmissao) -> dict:
        ...

    def cancelar_nfce(self, *, documento: NfceDocumento, motivo: str) -> dict:
        ...

    def inutilizar_numeracao(
        self, *, filial: Filial, serie: int, numero_inicial: int, numero_final: int, motivo: str
    ) -> dict:
        ...
```

---

# 9. Retorno padronizado dos clients

Todos os clients (SP, MG, RJ, ES, Mock) devem retornar:

```json
{
  "status": "INUTILIZADA" | "REJEITADA" | "ERRO",
  "codigo": "xxx",
  "mensagem": "Descrição da SEFAZ",
  "protocolo": "xxx", 
  "xml_enviado": "...",
  "xml_resposta": "...",
  "raw": { ... }
}
```

---

# 10. Persistência — `NfceInutilizacao`

Modelo recomendado:

```python
class NfceInutilizacao(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    filial_id = models.UUIDField()
    serie = models.IntegerField()
    numero_inicial = models.IntegerField()
    numero_final = models.IntegerField()
    motivo = models.TextField()
    protocolo = models.CharField(max_length=32, null=True)
    ambiente = models.CharField(max_length=20)
    xml_enviado = models.TextField()
    xml_resposta = models.TextField(null=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("filial_id", "serie", "numero_inicial", "numero_final")
```

Garante idempotência.

---

# 11. Auditoria da Inutilização

A auditoria deve registrar:

- `tipo_evento = "INUTILIZACAO"`
- `filial_id`
- `serie`
- `numero_inicial`
- `numero_final`
- `xml_enviado`
- `xml_resposta`
- `codigo`
- `mensagem`
- `protocolo`
- `ambiente`
- `user_id`
- `request_id`

(Ver `auditoria_nfce.md`)

---

# 12. Logs de Inutilização

Logbook:

- `nfce_inutilizacao_sucesso`
- `nfce_inutilizacao_falha`

### Exemplo sucesso:

```json
{
  "event": "nfce_inutilizacao_sucesso",
  "tenant_id": "...",
  "filial_id": "...",
  "serie": 1,
  "numero_inicial": 150,
  "numero_final": 160,
  "protocolo": "12345",
  "ambiente": "producao",
  "request_id": "..."
}
```

---

# 13. Ambiente MOCK

Em modo `mock`:

- Não há envio real para SEFAZ.
- O client retorna:
  - `"status": "INUTILIZADA"`
  - protocolo simulado
  - xml simulado
- Auditoria recomendada no QA.

---

# 14. Endpoints da API (Alta Nível)

```
POST /api/fiscal/nfce/inutilizar/

Body:
{
  "serie": 1,
  "numero_inicial": 151,
  "numero_final": 160,
  "motivo": "Falha técnica no terminal"
}
```

### Sucesso

```json
{
  "status": "INUTILIZADA",
  "protocolo": "123456",
  "serie": 1,
  "numero_inicial": 151,
  "numero_final": 160
}
```

### Rejeição SEFAZ

```json
{
  "error": "FISCAL_400x",
  "message": "Rejeição 563 - Número já utilizado.",
  "request_id": "..."
}
```

---

# 15. Regras Críticas a Observar

1. Não pode inutilizar número já autorizado.  
2. Não pode inutilizar faixa que já contém inutilização.  
3. Série inválida → erro SEFAZ.  
4. Motivo deve atender tamanho mínimo/máximo.  
5. Inutilização é irreversível.  
6. Pode inutilizar apenas numeração ainda não utilizada.  

---

# 16. Conclusão

Este documento define o padrão oficial para implementar inutilização de NFC-e no GetStart PDV:

- Modelo 65 / Layout 4.00  
- Clients por UF  
- Auditoria obrigatória  
- Logs padronizados  
- Idempotência garantida  
- Segurança operacional e fiscal  

A implementação deste fluxo garante conformidade total com a SEFAZ e integridade da numeração fiscal.
