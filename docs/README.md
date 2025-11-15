# GetStart PDV — Documentação do Backend

Este diretório contém a documentação oficial do **Backend GetStart PDV**, organizada por domínio técnico e de negócio.

A documentação está pensada para atender:

- 💻 **Backend / Arquitetura**
- 📱 **Aplicativo PDV / Frontend**
- 📊 **Fiscal / Contábil**
- ✅ **QA / Testes**
- 🔐 **Segurança / Compliance**
- 🔍 **Auditoria / Observabilidade**

---

## 1. Visão Geral da Estrutura

```text
docs/
├── api/
├── arquitetura/
├── dados/
├── fiscal/
├── fluxos/
├── qa/
├── security/
├── observabilidade/
└── auditoria/
1.1 api/ — Integração, Contratos e Erros

contratos.md
Descreve os contratos de API (padrões de request/response, autenticação, paginação, idempotência).

exemplos_payloads.md
Exemplos práticos de requests e responses para integrações.

openapi.yaml
Especificação formal da API (OpenAPI/Swagger).

dicionario_endpoints.md
Dicionário detalhado de endpoints, rota por rota, com regras de negócio, parâmetros e erros.

erros_api.md
Catálogo geral de códigos de erro da API (AUTH_*, TENANT_*, COMMON_*, etc.).

Quem usa mais: Backend, Frontend/PDV, Integradores, QA.

1.2 arquitetura/ — Visão Técnica e Domínios

overview.md
Visão macro da arquitetura (componentes principais, camadas, tecnologia).

dominios.md
Bounded contexts (tenants, usuário, fiscal, caixa, sync, etc.), responsabilidades e relacionamentos.

componentes.md
Componentes lógicos (serviços internos, apps Django, integrações externas).

sequencias_arquitetura.md
Sequências de chamadas internas para fluxos críticos (login, emissão NFC-e, sync).

Quem usa mais: Arquitetos, Devs backend, DevOps.

1.3 dados/ — Modelo de Dados

dicionario_dados.md
Campos, tipos e significado dos principais modelos de dados.

mapa_relacional.md
Visão relacional / ERD (como as tabelas se relacionam).

Quem usa mais: DBA, Backend, BI, Integradores.

1.4 fiscal/ — Regras Fiscais e NFC-e

regras_fiscais.md
Documento central das regras fiscais da NFC-e (reserva, pré-emissão, emissão, cancelamento, numeração).

erros_fiscais.md
Catálogo de erros FISCAL_* com cenários, causas e ações recomendadas.

xml_nfc_e_mock.md
Como funciona o modo mock de NFC-e e a evolução para emissão real.

guia_danfe_nfce.md
Guia completo do DANFE NFC-e (layout, campos, mapeamento XML → DANFE → PDV).

guia_implantacao_uf.md
Anotações por UF para implantação fiscal (pontos de atenção por estado).

guia_migracao_mock_para_sefaz.md
Guia passo a passo para migrar do modo mock para emissão real na SEFAZ.

auditoria_fiscal.docx
Documento formal de auditoria fiscal em formato DOCX (nível contador/auditor).

Quem usa mais: Fiscal/Contábil, Backend, Implantação.

1.5 fluxos/ — Fluxos de Negócio

fluxos_fiscais.md
Fluxos fiscais principais em nível de negócio.

bpmn_negocio.md
Fluxos completos em estilo BPMN (login, venda+NFCE, cancelamento, sync, caixa), com diagramas (mermaid) e narrativa.

Quem usa mais: Produto, Negócio, Devs, QA.

1.6 qa/ — Qualidade e Testes

estrategia_qa.md
Estratégia geral de QA (tipos de teste, pirâmide de testes, critérios de aceite).

testbook_fiscal.md
Cenários de teste focados em NFC-e (incluindo erros fiscais e bordas).

Quem usa mais: QA, Backend, Fiscal.

1.7 security/ — Segurança e Compliance

hardening_backend.md
Hardening de backend: Django, banco de dados, Docker, secrets, certificado A1.

hardening_api.md
Hardening de API: autenticação, rate limit, CORS, CSRF, validação de payload, erros.

compliance.md
LGPD, retenção de dados, logs, trilhas de auditoria, tratamento de incidente.

Quem usa mais: Segurança, DevOps, Backend, Jurídico/Compliance.

1.8 observabilidade/ — Logs e Monitoramento

logbook_eventos.md
Catálogo de eventos de log: o que logar, quando logar, formato e campos obrigatórios.

Quem usa mais: DevOps, Suporte, Backend, Auditoria.

1.9 auditoria/ — Auditoria Interna e Externa

modelo_auditoria_interna_externa.md
Modelo de auditoria: trilhas necessárias, relatórios, evidências e checklists.

Quem usa mais: Auditoria, Fiscal, Segurança, Gestão.

2. Como usar esta documentação

Para desenvolver novas features

Entender o domínio em arquitetura/dominios.md.

Checar impacto em dados em dados/dicionario_dados.md.

Ajustar contratos em api/contratos.md + openapi.yaml.

Se envolver NFC-e, revisar fiscal/regras_fiscais.md.

Atualizar fluxos em fluxos/bpmn_negocio.md.

Para investigar um incidente fiscal

Começar por observabilidade/logbook_eventos.md (eventos que devemos ver).

Revisar fiscal/regras_fiscais.md e fiscal/erros_fiscais.md.

Ver trilhas em auditoria/modelo_auditoria_interna_externa.md.

Para onboard de nova equipe

Ler arquitetura/overview.md.

Ler api/contratos.md + api/dicionario_endpoints.md.

Ler fiscal/regras_fiscais.md.

Ler security/hardening_backend.md + security/hardening_api.md.
