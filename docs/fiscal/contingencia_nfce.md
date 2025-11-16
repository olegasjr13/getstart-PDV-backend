# Contingência NFC-e — GetStart PDV (Modelo 65 / Layout 4.00)

## 1. Objetivo

Este documento define de forma completa o processo de **contingência NFC-e** no GetStart PDV, cobrindo:

- Contingência **EPEC**
- Contingência **Offline / FS-DA**
- Regras do Modelo 65 / Layout 4.00
- Fluxos operacionais no PDV
- Estratégia de reconciliação com SEFAZ
- Logs e auditoria
- Comportamento por ambiente (mock/homolog/producao)
- Pontos planejados para o futuro do projeto (não incluídos no MVP)

---

# 2. O que é contingência NFC-e?

A contingência é usada quando **não é possível emitir NFC-e normalmente**, por:

- indisponibilidade da SEFAZ
- falha de conexão do contribuinte
- oscilação de rede
- timeout ou erro de assinatura
- bloqueios no certificado
- instabilidade de internet do PDV

A solução fiscal exige que a venda seja concluída **mesmo sem SEFAZ**, desde que siga os modos oficiais:

- **EPEC** (Evento Prévio de Emissão em Contingência)
- **Contingência Offline (FS-DA / Documento Auxiliar)**

> ⚠ Importante:  
> No Modelo 65 (NFC-e), a maior parte das UFs **não utiliza FS-DA**, adotando apenas online + EPEC.  
> Ainda assim, incluímos ambos para compatibilidade nacional e expansão futura.

---

# 3. Escopo no GetStart PDV

### MVP (Fase atual)
- ❌ Não implementaremos contingência (nem EPEC nem Offline).
- ✔ Documentação preparada para implementação futura.
- ✔ Arquitetura já permite adição de uma terceira rota de emissão.

### Fase 2 (Próxima etapa após MVP)
- ✔ Implementar EPEC (mais simples e aceito pela maioria das UFs).
- ❌ Offline FS-DA só se necessário para UF específica.

---

# 4. Tipos de contingência NFC-e

## 4.1. **EPEC — Evento Prévio de Emissão em Contingência**

O PDV envia:

- **uma versão simplificada da NFC-e** para a SEFAZ nacional (SVRS)
- recebe protocolo EPEC
- entrega DANFE EPEC ao cliente

Quando a SEFAZ local voltar:

- a NFC-e deve ser reenviada com base no EPEC recebido

### Estados que suportam EPEC
- SP → sim
- MG → sim
- RJ → sim
- ES → sim

### Vantagens
- Autorização oficial ANTES da venda ser finalizada
- Baixo risco de rejeição posterior
- Reconciliação simples
- Evita numeração perdida

### Desvantagens
- Requer envio para SEFAZ Virtual
- Depende de certificado A1 válido

---

## 4.2. **Contingência Offline (FS-DA / Offline)**

A venda é emitida **com XML completo**, mas:

- fica armazenada localmente
- DANFE offline é entregue ao cliente
- quando SEFAZ voltar, a NFC-e é enviada normalmente

### Estados que ainda aceitam FS-DA para NFC-e
Pouquíssimos — a maioria exige apenas EPEC.

Offline tem riscos:

- maior probabilidade de rejeição posterior
- exige **reenvio obrigatório**
- exige reconciliação local mais complexa
- exige armazenamento seguro das vendas

---

# 5. Fluxo Geral de Contingência (Visão Alto Nível)

```
[1] Tentativa normal de emissão
        ↓ falha (timeout, rejeição técnica, indisponibilidade)
[2] PDV pergunta ao backend o modo de contingência
        ↓
[3] Backend decide: EPEC / Offline / Nenhum
        ↓
[4] Gera documento de contingência (XML parcial ou completo)
        ↓
[5] Armazena e devolve ao PDV
        ↓
[6] PDV imprime DANFE EPEC ou Offline
        ↓
[7] Quando SEFAZ voltar → reconciliação automática
        ↓
[8] Auditoria + persistência definitiva
```

---

# 6. Regras que Disparam Contingência

O backend deve detectar contingência quando ocorrer:

- Timeout de SEFAZ (`FISCAL_5005`)
- Erro de comunicação (`FISCAL_5001`)
- Certificado inválido temporariamente
- Falha de DNS
- Indisponibilidade de host SEFAZ
- Endpoint EPEC disponível mas padrão indisponível
- Falha de assinatura do XML
- Erro no protocolo de retorno

---

# 7. Estratégia Oficial do GetStart PDV

Para manter integridade fiscal e simplicidade na operação:

## 7.1. Modo padrão

- **Usar EPEC como contingência oficial**
- FS-DA/Offline apenas quando EPEC não for aceito pela UF

## 7.2. Prioridade na emissão

```
1º Tentativa normal SEFAZ
2º Repetir com timeout maior
3º SEFAZ indisponível → EPEC
4º Se EPEC indisponível → fallback local (Offline) [fase futura]
```

## 7.3. Operação do PDV durante contingência

O PDV nunca decide sozinho.  
Ele envia erro ao backend, e o backend responde:

```
"modo_contingencia": "epec" | "offline" | null
```

---

# 8. Estrutura de XML da Contingência

## 8.1. EPEC (Evento)

Tags principais:

- `<evento>`  
- `<infEvento>`  
- `<detEvento>`  
- `tpEvento = "110140"` (varia por UF)  
- Contém **dados resumidos** da NFC-e real  

## 8.2. Offline (FS-DA)

O XML é o **mesmo XML normal**, apenas marcado como contingência:

- `tpEmis = 9` (Emissão em contingência offline)
- Deve conter hora e justificativa

---

# 9. SefazClient — Ajustes Necessários

O protocolo deve prever emissão em contingência:

```python
class SefazClientProtocol(Protocol):
    def emitir_nfce(self, *, pre_emissao: NfcePreEmissao) -> dict: ...

    def cancelar_nfce(self, *, documento: NfceDocumento, motivo: str) -> dict: ...

    def inutilizar_numeracao(self, *, filial: Filial, serie: int, numero_inicial: int, numero_final: int, motivo: str) -> dict: ...

    def emitir_epec(self, *, pre_emissao: NfcePreEmissao) -> dict:
        ...
```

E futuramente:

```python
def emitir_offline(self, *, pre_emissao: NfcePreEmissao) -> dict:
    ...
```

---

# 10. Persistência

### 10.1. EPEC

Criar modelo:

```python
class NfceEpec(models.Model):
    filial_id = UUID
    chave = str
    numero = int
    serie = int
    motivo = str
    protocolo = str
    xml_enviado = text
    xml_resposta = text
    criado_em = datetime
```

### 10.2. Offline

Requer:

- Armazenamento seguro do XML  
- Flag "pendente de envio"  

---

# 11. Reconciliação Pós-Contingência

Assim que a SEFAZ voltar:

```
[1] Backend lista documentos em contingência
[2] Reenvia NFC-e ou evento correspondente
[3] Atualiza NfceDocumento
[4] Registra auditoria
[5] Atualiza logs
```

Rejeições posteriores devem:

- Emitir auditoria
- Seren tratadas no painel fiscal
- Nunca apagar XML gerado originalmente

---

# 12. Logs da Contingência

### 12.1. Sucesso EPEC

Evento:

```
nfce_epec_sucesso
```

### 12.2. Falha EPEC

```
nfce_epec_falha
```

### 12.3. Sucesso Offline

```
nfce_offline_registrado
```

### 12.4. Falha de reconciliação

```
nfce_contingencia_reconciliacao_falha
```

---

# 13. Auditoria

Tudo relacionado a contingência deve ser auditado:

- Tentativa normal
- Entrada em contingência
- Evento EPEC
- Reenvio posterior
- XML enviado/recebido
- Protocolo
- Ambiente e UF
- request_id
- usuário

---

# 14. Impactos Fiscais e Operacionais

### 14.1. Numeração

Contingência **não pode** quebrar sequência fiscal.

Numeração deve ser:

- reservada
- usada
- registrada em EPEC ou Offline
- posteriormente enviada à SEFAZ

### 14.2. Operação do PDV

O PDV deve:

- imprimir o tipo correto de DANFE (EPEC ou Offline)
- indicar contingência ao operador
- registrar hora exata local
- impedir edição posterior

---

# 15. Ambiente MOCK

No ambiente `"mock"`:

- contingência é simulada
- EPEC retorna sucesso por padrão
- Offline é permitido sem regras rígidas
- Usado apenas para QA e testes automáticos

---

# 16. Conclusão

Este documento define todas as regras necessárias para implementar contingência NFC-e no GetStart PDV:

- EPEC (fluxo principal)
- Offline (opcional e futuro)
- XML, auditoria, logs, reconciliação
- Sequência fiscal protegida
- Comportamento do PDV em condições reais

A implementação ocorrerá após estabilização do MVP fiscal.
