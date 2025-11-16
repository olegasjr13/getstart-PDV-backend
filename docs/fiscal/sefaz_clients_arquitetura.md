# Arquitetura dos Clients SEFAZ — GetStart PDV

## 1. Objetivo

Este documento define a **arquitetura oficial dos clients SEFAZ** usados no módulo de NFC-e do GetStart PDV.  
Aqui detalhamos:

- O contrato único (`SefazClientProtocol`)
- O `BaseSefazClient`
- Clients por UF (SP, MG, RJ, ES)
- Client MOCK
- A factory `get_sefaz_client`
- Fluxo interno de emissão
- Boas práticas e padrões obrigatórios

Este arquivo serve como referência para desenvolvimento, QA e expansão fiscal.

---

## 2. Visão Geral da Arquitetura

A comunicação com a SEFAZ segue uma arquitetura **plugável por UF**, permitindo que cada unidade federativa tenha:

- Suas próprias URLs
- Certificados específicos
- Regras internas
- Particularidades de schema

Estrutura:

```
SefazClientProtocol (contrato)
└── BaseSefazClient (comportos comuns)
    ├── SefazClientMock
    ├── SefazClientSP
    ├── SefazClientMG
    ├── SefazClientRJ
    └── SefazClientES
```

A escolha do client é feita via factory:

```
client = get_sefaz_client(uf, ambiente, filial)
```

O `NfceEmissaoService` **não sabe** qual client está usando  
(mock, homolog ou produção). Ele apenas chama:

```
client.emitir_nfce(pre_emissao)
```

---

## 3. Contrato Oficial — `SefazClientProtocol`

Todos os clients devem implementar:

```python
class SefazClientProtocol(Protocol):
    def emitir_nfce(self, *, pre_emissao: NfcePreEmissao) -> dict:
        ...
```

### 3.1. Entrada

A entrada é sempre uma instância de `NfcePreEmissao`, que contém:

- filial
- terminal
- número / série
- payload completo da venda
- request_id

### 3.2. Saída Padronizada

Todos os clients **devem retornar** um dicionário com:

```json
{
  "status": "AUTORIZADA" | "REJEITADA" | "ERRO",
  "codigo": "<codigo_retorno>",
  "mensagem": "<mensagem_humana>",
  "chave": "<chave_44_digitos_ou_none>",
  "protocolo": "<protocolo_ou_none>",
  "xml_enviado": "<xml_assinado>",
  "xml_resposta": "<xml_resposta>",
  "raw": { ... }
}
```

Isso garante que o `NfceEmissaoService` seja independente da UF.

---

## 4. BaseSefazClient

O `BaseSefazClient` implementa:

- Montagem de XML (builder comum)
- Assinatura com certificado A1
- Geração de cUF, cNF, chave de acesso
- Validações de campos obrigatórios
- Serialização/deserialização XML
- Logging padrão

Especializações por UF apenas sobrescrevem:

- URLs
- Regras específicas de schema
- Header SOAP (quando houver)
- Processamento de resposta

---

## 5. Clients por UF

Cada client deve fornecer:

### 5.1. `SefazClientSP`
- Endpoint SP Homolog
- Endpoint SP Produção
- Particularidades:
  - Schema SP para NFC-e
  - Timeout padrão SP

### 5.2. `SefazClientMG`
- Endpoints MG
- Processamento diferenciado de rejeições

### 5.3. `SefazClientRJ`
- URLs SOAP específicas
- Resposta diferente para sucesso/rejeição

### 5.4. `SefazClientES`
- Endpoints ES
- Certas rejeições padronizadas

---

## 6. Client MOCK — `SefazClientMock`

O mock simula:

- Autorização
- Rejeição configurada
- Erro técnico
- Geração fake de XML e chave

Útil para:

- Desenvolvimento (`dev`)
- QA sem certificado
- Testes automatizados

---

## 7. Factory — `get_sefaz_client()`

O roteamento é feito por:

- `filial.uf` → SP/MG/RJ/ES
- `filial.nfce_ambiente` → mock/homolog/producao

Pseudocódigo:

```python
def get_sefaz_client(uf, ambiente, filial):
    if ambiente == "mock":
        return SefazClientMock()

    if uf == "SP":
        return SefazClientSP(filial)
    if uf == "MG":
        return SefazClientMG(filial)
    if uf == "RJ":
        return SefazClientRJ(filial)
    if uf == "ES":
        return SefazClientES(filial)

    raise NotImplementedError(f"UF {uf} não implementada")
```

---

## 8. Responsabilidade do Emissor (`NfceEmissaoService`)

O serviço:

1. Carrega a pré-emissão
2. Busca filial e terminal
3. Identifica ambiente
4. Seleciona o client
5. Gera XML
6. Assina XML
7. Envia XML via client
8. Persistência do documento fiscal
9. Auditoria
10. Logging

O service **nunca** deve ter lógica fiscal específica de UF.

---

## 9. Logs Obrigatórios

Todos os clients devem emitir:

- `nfce_emissao_mock_sucesso`
- `nfce_emissao_mock_erro`
- `nfce_emissao_sefaz_sucesso`
- `nfce_emissao_sefaz_rejeitada`
- `nfce_emissao_sefaz_erro`

Campos obrigatórios:

- tenant_id
- filial_id
- terminal_id
- user_id
- request_id
- numero
- serie

---

## 10. Auditoria Obrigatória

Somente emissão real:

- AUTORIZADA → grava auditoria
- REJEITADA → grava auditoria
- ERRO (técnico) → opcional

Mock:

- Dev → opcional
- QA → recomendado

---

## 11. Evolução Futura

Os clients devem evoluir para:

- Validar XML contra XSD offline
- Acompanhar contingência (EPEC)
- Implementar cancelamento e inutilização
- Tratar regras fiscais avançadas

Quando qualquer mudança afetar o contrato do client,  
**este documento deve ser atualizado.**
