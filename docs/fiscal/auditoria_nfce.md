# Auditoria de NFC-e — GetStart PDV

## 1. Objetivo

Este documento define o **modelo oficial de auditoria fiscal** para o módulo de NFC-e no GetStart PDV, garantindo:

- Conformidade com requisitos fiscais e contábeis.
- Rastreabilidade ponta a ponta (pré-emissão → emissão → retorno SEFAZ).
- Investigação de incidentes e divergências.
- Alinhamento com logs JSON e `request_id`.
- Auditoria completa em ambiente **homologação** e **produção**.
- Suporte para ambientes **mock** em QA.

Ele complementa:

- `regras_fiscais.md`
- `padroes_logs_backend.md`
- `logbook_eventos.md`
- `sefaz_clients_arquitetura.md`
- `ambientes_homolog_producao.md`

---

# 2. O que deve ser auditado?

A auditoria registra **eventos fiscais permanentes**, diferentes dos logs.

### 2.1. Eventos obrigatórios

| Evento | Auditoria? | Motivo |
|--------|------------|--------|
| **Emissão autorizada** | ✔ Obrigatória | Documento fiscal válido |
| **Rejeição SEFAZ** | ✔ Obrigatória | Prova do evento e do erro |
| **Erro técnico SEFAZ** | Recomendado | Diagnóstico/troubleshooting |
| **Cancelamento** | ✔ Obrigatória | Ato fiscal válido |
| **Inutilização** | ✔ Obrigatória | Ato fiscal válido |

### 2.2. Eventos opcionais

| Evento | Auditoria? |
|--------|------------|
| Pré‑emissão | opcional |
| Mock (dev) | opcional |
| Mock (QA) | recomendado |

---

# 3. Modelo de Dados — `NfceAuditoria`

O modelo recomendado é:

```python
class NfceAuditoria(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Contexto do tenant
    tenant_id = models.CharField(max_length=14)  # CNPJ raiz
    schema_name = models.CharField(max_length=64)

    # Identificação fiscal
    filial_id = models.UUIDField()
    terminal_id = models.UUIDField()
    numero = models.IntegerField()
    serie = models.IntegerField()
    chave = models.CharField(max_length=44, null=True, blank=True)

    # Tipo de evento auditado
    tipo_evento = models.CharField(max_length=50, choices=[
        ("EMISSAO_AUTORIZADA", "Emissão Autorizada"),
        ("EMISSAO_REJEITADA", "Emissão Rejeitada"),
        ("EMISSAO_ERRO", "Erro Técnico na Emissão"),
        ("CANCELAMENTO", "Cancelamento"),
        ("INUTILIZACAO", "Inutilização"),
    ])

    # Dados de retorno da SEFAZ / MOCK
    codigo = models.CharField(max_length=10, null=True, blank=True)
    mensagem = models.TextField(null=True, blank=True)
    protocolo = models.CharField(max_length=32, null=True, blank=True)

    ambiente = models.CharField(max_length=20)  # mock/homolog/producao
    uf = models.CharField(max_length=2)

    # XML
    xml_enviado = models.TextField()
    xml_resposta = models.TextField(null=True, blank=True)

    # Request/Usuário
    request_id = models.UUIDField()
    user_id = models.IntegerField(null=True, blank=True)

    criado_em = models.DateTimeField(auto_now_add=True)
```

---

# 4. Regras de Auditoria

## 4.1. Emissão AUTORIZADA

Registrar **sempre**:

- `tipo_evento = "EMISSAO_AUTORIZADA"`
- `chave`
- `protocolo`
- `codigo = 100 ou equivalente`
- `xml_enviado`
- `xml_resposta`
- `ambiente` (homolog/producao/mock)
- `request_id`
- `tenant_id`, `filial_id`, `terminal_id`

## 4.2. Emissão REJEITADA

Registrar:

- `tipo_evento = "EMISSAO_REJEITADA"`
- `codigo` (ex.: 106, 215, 999 etc.)
- `mensagem`
- `xml_enviado` (mesmo rejeitado)
- `xml_resposta`
- `chave = None`
- `protocolo = None`

Obrigatório em **homologação** e **produção**.

## 4.3. Erro técnico

Registrar:

- `tipo_evento = "EMISSAO_ERRO"`
- `codigo = <erro tecnico>`
- `mensagem`
- `xml_enviado` quando existir
- `xml_resposta = ""` se não houver retorno

## 4.4. Cancelamento

Registrar:

- `tipo_evento = "CANCELAMENTO"`
- Dados da chave cancelada
- XML de cancelamento
- Protocolo de cancelamento

## 4.5. Inutilização

Registrar:

- `tipo_evento = "INUTILIZACAO"`
- Faixa inutilizada
- XML enviado
- Protocolo SEFAZ

---

# 5. Relação com Logs

A auditoria **não substitui logs**.

Cada entrada de auditoria deve corresponder a um evento no logbook:

| Log | Auditoria | Descrição |
|-----|-----------|-----------|
| `nfce_emissao_sefaz_sucesso` | ✔ | Sempre |
| `nfce_emissao_sefaz_rejeitada` | ✔ | Sempre |
| `nfce_emissao_sefaz_erro` | recomendado | Erro técnico |
| `nfce_emissao_mock_*` | opcional | Dependente do ambiente |

Ambos devem compartilhar o mesmo **request_id**.

---

# 6. Fluxo da Auditoria dentro do `NfceEmissaoService`

Fluxo interno:

```
client = get_sefaz_client(...)
res = client.emitir_nfce(pre_emissao)

if res.status == AUTORIZADA:
    salvar_auditoria_autorizada(res)
elif res.status == REJEITADA:
    salvar_auditoria_rejeicao(res)
else:
    salvar_auditoria_erro(res)
```

O service **não deve** decidir o formato do XML, apenas armazenar.

---

# 7. Garantias e Integridade

Requisitos obrigatórios:

- Auditoria **não pode ser alterada ou removida**.
- Apenas registros novos podem ser inseridos.
- Os dados devem ser exportáveis para análise.
- A auditoria deve ficar **dentro do schema do tenant**, para isolamento.

---

# 8. Auditoria e Multitenancy

A auditoria deve:

- Ser armazenada dentro do schema do tenant (`schema_context`).
- Isolar eventos por empresa.
- Permitir auditorias externas sem risco de vazamento entre tenants.

Exemplo:

```python
with schema_context(tenant.schema_name):
    NfceAuditoria.objects.create(...)
```

---

# 9. Relacionamento com Número/Série

A auditoria deve registrar:

- `numero`
- `serie`
- `filial_id`
- `terminal_id`

Permite rastrear:

- Divergências
- Falhas de emissão
- Reemissões indevidas

---

# 10. Exportação e Retenção de Dados

Recomendações:

- Retenção mínima: **5 anos** (prazos fiscais)
- Opção de exportação:
  - JSON
  - XML
  - CSV
- API de consulta interna pode ser criada (com permissão elevada)

---

# 11. Auditoria em ambiente MOCK

Regra:

- Dev: **opcional**
- QA: **recomendado**
- Produção: **proibido usar mock**

O mock deve ser claramente identificado em:

- `ambiente = "mock"`
- `raw.mock = true`

---

# 12. Conclusão

A auditoria NFC-e garante:

- Conformidade fiscal
- Rastreabilidade
- Diagnóstico rápido
- Segurança e isolamento por tenant
- Integração com logs e Sentry

Qualquer mudança nos processos de emissão deve atualizar este documento.
