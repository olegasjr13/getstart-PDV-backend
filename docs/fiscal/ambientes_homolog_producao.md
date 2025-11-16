# Ambientes de Homologação e Produção — GetStart PDV (NFC-e)

## 1. Objetivo

Este documento define de forma clara e padronizada **como o backend do GetStart PDV gerencia ambientes fiscais** para emissão de NFC-e:

- **MOCK** (ambiente interno de desenvolvimento/QA)
- **HOMOLOGAÇÃO** (SEFAZ oficial, ambiente de testes)
- **PRODUÇÃO** (SEFAZ oficial, emissão válida)

Aqui definimos:

- Como cada ambiente funciona
- Onde isso é configurado
- Regras por FILIAL
- Requisitos técnicos
- Controles de segurança
- Relação com emissão NFC-e e SefazClient
- Processo de habilitação para produção

Este documento complementa:

- `regras_fiscais.md`
- `xml_nfc_e_mock.md`
- `sefaz_clients_arquitetura.md`
- `auditoria_nfce.md`

---

# 2. Ambientes Disponíveis

Cada filial opera **exclusivamente em um dos ambientes abaixo**:

| Ambiente     | Nome interno | Uso |
|--------------|--------------|-----|
| MOCK         | `"mock"`     | Dev/QA sem SEFAZ |
| HOMOLOGAÇÃO  | `"homolog"`  | Testes fiscais reais com SEFAZ |
| PRODUÇÃO     | `"producao"` | Emissão oficial da NFC-e |

---

# 3. Campo Oficial: `filial.nfce_ambiente`

A tabela `Filial` contém o campo responsável por selecionar o ambiente:

```python
class Filial(models.Model):
    ...
    nfce_ambiente = models.CharField(
        max_length=20,
        choices=[
            ("mock", "Mock"),
            ("homolog", "Homologação"),
            ("producao", "Produção"),
        ],
        default="mock",
    )
```

### 3.1. Regra principal

> **A emissão NFC-e SEMPRE usa o ambiente configurado na filial.**

O PDV/app não decide isso.  
O backend seleciona automaticamente o client via:

```
client = get_sefaz_client(uf=filial.uf, ambiente=filial.nfce_ambiente, filial=filial)
```

---

# 4. Ambiente MOCK

O ambiente `"mock"` é usado em:

- Desenvolvimento local
- Servidores QA
- Testes automatizados
- Seeds (`profile=dev`, `profile=qa`)
- Cenários controlados de rejeição/erro

### 4.1. Características do MOCK

- Não usa certificado A1
- Não envia XML para SEFAZ real
- Gera chave de acesso falsa, porém válida
- Permite simular:
  - Emissão autorizada
  - Rejeição configurada
  - Erro técnico
  - Timeout, exceção, etc.

### 4.2 Logs e auditoria

- Logs:
  - `nfce_emissao_mock_sucesso`
  - `nfce_emissao_mock_erro`
- Auditoria:
  - Dev → opcional
  - QA → recomendado

---

# 5. Ambiente HOMOLOGAÇÃO

É o ambiente de testes oficial da SEFAZ.

### 5.1. Requisitos mínimos para usar Homologação

A filial deve ter:

- Certificado A1 válido (`filial.a1_certificate`)
- Data de expiração válida (`a1_expires_at`)
- CSC de homologação
- CNPJ/IE válidos
- Atualização da série e numeração

### 5.2. Características

- Envia XML real para SEFAZ Homologação
- SEFAZ valida:
  - Schema
  - Regras fiscais simples
  - Integridade dos campos

### 5.3 Logs

- `nfce_emissao_sefaz_sucesso`
- `nfce_emissao_sefaz_rejeitada`
- `nfce_emissao_sefaz_erro`

### 5.4 Auditoria

Na homologação:

- Auditoria é **obrigatória**
- Permite rastrear:
  - XML enviado
  - XML de retorno
  - Protocolo
  - Chave
  - Motivo de rejeição

---

# 6. Ambiente PRODUÇÃO

Ambiente oficial da SEFAZ — **documentos emitidos têm valor fiscal**.

### 6.1. Requisitos obrigatórios

Para habilitar o ambiente de produção em uma filial:

1. Certificado A1 válido e testado
2. CSC válido de produção
3. Série definida e consistente
4. Filial com dados fiscais cadastrados:
   - CNPJ completo
   - IE
   - Regime tributário (Normal, Simples)
   - Endereço oficial cadastrado
5. Numeração sincronizada
6. Teste prévio de homologação aprovado

### 6.2. Segurança

O backend deve:

- Registrar auditoria completa
- Emitir logs padronizados de produção
- Validar acesso por tenant/usuário
- Bloquear PDVs/terminais inativos
- Impedir alteração dinâmica do ambiente sem permissão administrativa

### 6.3. Logs obrigatórios

- `nfce_emissao_sefaz_sucesso`
- `nfce_emissao_sefaz_rejeitada`
- `nfce_emissao_sefaz_erro`

### 6.4. Auditoria obrigatória

Todo evento de:

- Emissão AUTORIZADA
- Emissão REJEITADA
- Cancelamento
- Inutilização

deve ser registrado em:

`NfceAuditoria`

Detalhado em `auditoria_nfce.md`.

---

# 7. Processo para Ativar Homologação ou Produção

### 7.1. Passo 1 — Configurar Certificado A1

- Upload do certificado `.pfx` (criptografado)
- Senha armazenada com segurança
- Conversão para PEM (em memória)
- Validação da cadeia

### 7.2. Passo 2 — Cadastrar CSC

- CSC de homologação e produção
- Registrar token/ID CSC

### 7.3. Passo 3 — Validar Dados da Filial

- CNPJ
- IE
- Endereço
- Regime tributário
- UF

### 7.4. Passo 4 — Liberar ambiente

Somente usuários com permissão administrativa podem alterar:

```
filial.nfce_ambiente = "homolog"   # ou "producao"
```

### 7.5. Passo 5 — Teste obrigatório

Antes de ativar produção:

- Emitir 1 NFC-e em homologação
- Verificar retorno, protocolo, assinatura

---

# 8. Como o sistema escolhe o ambiente

O backend segue exatamente esta regra:

```
ambiente = filial.nfce_ambiente
client = get_sefaz_client(filial.uf, ambiente, filial)
response = client.emitir_nfce(...)
```

Ou seja:

- O PDV nunca controla o ambiente.
- O ambiente não é enviado no payload.
- O ambiente só depende da FILIAL e da configuração do tenant.

---

# 9. Resumo Técnico por Ambiente

| Ambiente | Certificado A1 | Envio real | Auditoria | Logs obrigatórios |
|----------|-----------------|------------|-----------|-------------------|
| mock | Não | Não | Dev: opcional / QA: recomendado | `nfce_emissao_mock_*` |
| homolog | Sim | Sim | Obrigatória | `nfce_emissao_sefaz_*` |
| producao | Sim | Sim | Obrigatória | `nfce_emissao_sefaz_*` |

---

# 10. Evolução Planejada

Na evolução do módulo fiscal:

- Contingência EPEC
- Contingência offline FS-DA
- Múltiplos CSCs por ambiente
- Controle de múltiplos certificados por filial
- Auditoria completa por operação (via `auditoria_nfce.md`)

Quando qualquer parte desta arquitetura evoluir, **este documento deve ser atualizado**.
