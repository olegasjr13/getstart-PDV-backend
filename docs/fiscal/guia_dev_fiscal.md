# Guia de Desenvolvimento Fiscal — GetStart PDV Backend

## 1. Objetivo

Este documento descreve **como o módulo fiscal (NFC-e)** do GetStart PDV funciona no backend, detalhando:

- Arquitetura interna
- Fluxo fiscal completo (reserva → pré-emissão → emissão → cancelamento)
- Regras de negócio já implementadas no código
- Padrões obrigatórios para desenvolvimento
- Onde e como implementar novas regras fiscais
- Orientações para testes fiscais (unitários, integração e multi-tenant)
- Diferenças entre modo MOCK e modo SEFAZ real
- Como será a evolução para produção

Este guia é **o documento principal para desenvolvedores backend que atuam em fiscal**.

---

# 2. Arquitetura do Módulo Fiscal

O módulo fiscal está localizado em:

fiscal/
├── models/
│ ├── nfce_reserva_model.py
│ ├── nfce_pre_emissao_model.py
│ ├── ...
├── services/
│ ├── numero_service.py
│ ├── pre_emissao_service.py
│ ├── emissao_service.py
│ ├── utils/
├── views/
│ ├── nfce_views.py
│ ├── nfce_pre_emissao_views.py
├── tests/
│ ├── test_nfce_reserva.py
│ ├── test_nfce_multitenant_isolation.py
│ ├── test_nfce_idempotencia_mesmo_request_id.py
└── ...


## 2.1 Padrão clean: Views finas + Services gordos

O módulo fiscal segue fielmente o padrão:



View → Service → Model


### Exemplos reais (do projeto):

- `NfceNumeroService` cuida exclusivamente de:
  - reserva de numeração
  - idempotência por request_id
  - regra de série/filial/terminal

- `NfcePreEmissaoService`:
  - valida totais, valores, itens, pagamentos
  - consolida informações obrigatórias no banco
  - garante integridade fiscal

- `NfceEmissaoService`:
  - gera o XML mock
  - aplica parâmetros fiscais unidos da pré-emissão
  - gera chave, protocolo e QR Code

---

# 3. Fluxo Fiscal Completo

O fluxo fiscal implementado hoje é:



RESERVA → PRÉ-EMISSÃO → EMISSÃO (MOCK)


Posteriormente:



CANCELAMENTO


---

## 3.1 RESERVA — `POST /api/v1/fiscal/nfce/reserva`

### Objetivo
Garantir **sequencialidade fiscal e idempotência**.

### Regras implementadas:

- (R1) Mesma combinação
  `tenant + filial + terminal + série + request_id`
  **sempre devolve a mesma reserva**.
- (R2) Cada combinação possui **seu próprio contador de número**.
- (R3) NUNCA pode existir “buraco” de numeração.
- (R4) Só pode reservar se o terminal estiver ativo.
- (R5) Só pode reservar se o tenant estiver configurado corretamente.

### Trechos reais (resumidos):

```python
reserva = NfceNumeroService(tenant).reservar(
    request_id=request_id,
    filial=filial,
    terminal=terminal,
    serie=serie
)

Persistência:

Modelo NfceReserva recebe:

número

série

request_id

vínculo com filial/terminal

3.2 PRÉ-EMISSÃO — POST /api/v1/fiscal/nfce/pre-emissao
Objetivo

Consolidar todos os dados de venda ANTES da emissão.

Validações implementadas:

(V1) Deve existir reserva válida.

(V2) Totais devem bater (valor_total == soma itens + pagamentos).

(V3) Cada item deve ter:

quantidade > 0

valor_unitário > 0

impostos obrigatórios

(V4) Cada pagamento deve ser válido:

tipo permitido

valor ≥ 0

(V5) Pré-emissão deve ser idempotente para o mesmo request_id.

Persistência

Modelos:

NfcePreEmissao

NfcePreEmissaoItem

NfcePreEmissaoPagamento

3.3 EMISSÃO — POST /api/v1/fiscal/nfce/emissao
Objetivo

Gerar XML mock seguindo o padrão da NFC-e real.

Comportamento implementado:

Carrega dados da pré-emissão

Envia para serviço EmissaoXmlMockBuilder

Gera:

XML mock completo

chave

protocolo

QR Code

Salva no modelo NfceEmitida

O módulo mock já implementa:

Tag raiz <NFe>

Grupos de identificação

Emissão no modo homologação

Montagem de chave com:

UF 35

CNPJ do tenant

série

número

etc.

4. Regras Fiscais Implementadas

Regras do service que já existem no código:

Código	Descrição
FISCAL_4001	Falha ao verificar terminal
FISCAL_4002	Solicitação duplicada (idempotência)
FISCAL_4003	Divergência de totais
FISCAL_4004	Item inválido
FISCAL_4005	Pagamento inválido
FISCAL_4006	Pré-emissão não encontrada
FISCAL_4007	Reserva não encontrada
FISCAL_4008	Terminal inativo
FISCAL_4010	Tentativa de emitir sem pré-emissão

Essas regras devem ser mantidas no nível de service.

5. Implementação de Novas UF

Para gerar NFCE real futuramente:

Criar UfRules com fábrica:

class UFRulesFactory:
    def get(self, uf):
        return SPUFRules() ...


Parametrizar:

alíquotas

CFOPs

naturezas

regras específicas

Nunca duplicar código entre UFs.

6. Modo MOCK x Modo SEFAZ real
6.1 MOCK (ativo hoje)

XML é gerado localmente

protocolo é aleatório

chave é válida mas não registrada na SEFAZ

fluxo 100% controlado internamente

6.2 Modo Real (próximo passo)

usar certificado A1

integração com webservice SEFAZ

timeout/retentativas

consulta de recibo

offline com DANFE de contingência

7. Padrão para Evolução Fiscal
Para novas features fiscais:

atualizar regras_fiscais.md

criar tests:

reserva

pré

emissão

idempotência

dois tenants

adicionar logs obrigatórios:

fiscal_reserva_criada

fiscal_pre_emissao_criada

fiscal_emitida

incluir no Logbook e QA

8. Conclusão

Este guia formaliza toda a arquitetura fiscal implementada hoje no GetStart PDV, com detalhes técnicos e regras funcionais.
Qualquer evolução deve seguir essas bases para garantir consistência, estabilidade e segurança fiscal.
