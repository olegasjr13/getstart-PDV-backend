# Regras Fiscais — GetStart PDV

## 1. Objetivo

Este documento consolida todas as regras fiscais aplicáveis ao módulo de NFC-e no GetStart PDV.
Ele define:

- O escopo fiscal do MVP.
- Como a emissão de NFC-e deve funcionar por UF.
- Estrutura de pré-emissão e emissão.
- Regras de validação, ambiente, numerário e regras operacionais.
- Comportamento esperado de mock, homologação e produção.
- Arquitetura do emissor via *SEFAZ Client* por UF.
- Multitenancy e impacto fiscal por filial.
- Auditoria e rastreabilidade.

Este documento serve como **fonte oficial** para desenvolvimento, QA e integração com SEFAZ.

---

# 2. Escopo Fiscal do MVP

O MVP do módulo fiscal atenderá **quatro unidades federativas**:

- **SP** — São Paulo
- **MG** — Minas Gerais
- **RJ** — Rio de Janeiro
- **ES** — Espírito Santo

Essas UFs cobrem grande parte do varejo nacional e possuem regras relativamente alinhadas para NFC-e, facilitando o início do projeto.

### 2.1. O que está incluído no MVP

- Emissão de NFC-e usando:
  - Mock interno (dev/QA)
  - SEFAZ Homologação
  - SEFAZ Produção
- Fluxo:
  1. **Reserva de número**
  2. **Pré-emissão**
  3. **Emissão**
- Preparação para cancelamento e inutilização.
- Auditoria fiscal por evento.

### 2.2. O que NÃO está incluído no MVP (mas será preparado)

- Contingência offline (EPEC/FS-DA).
- DIFAL interestadual completo.
- Múltiplos CSCs por filial.
- Regras fiscais de ICMS avançado e ST específicas de cada produto.
- Impressão DANFE simplificada.

---

# 3. Multitenancy e Contexto Fiscal

### 3.1. Tenant → Filiais → Terminais

Cada tenant pode possuir:

- Múltiplas filiais, cada uma em uma **UF diferente**
- Múltiplos terminais por filial
- Cada filial pode operar em **ambiente diferente**:
  - `homolog`
  - `producao`

### 3.2. Dados fiscais são sempre no contexto da **filial**

Toda emissão NFC-e depende da filial, porque é ela que possui:

- CSC (Código de Segurança do Contribuinte)
- CNPJ / inscrição estadual
- Certificado A1
- UF e ambiente SEFAZ
- Série e controle de númeração

No código, isso está refletido nas entidades:

- `NfceNumeroReserva`
- `NfcePreEmissao`
- `NfceEmissaoService`
- `Filial`
- `Terminal`

---

# 4. Fluxo Fiscal Oficial (NFC-e)

A emissão de NFC-e no GetStart PDV segue o fluxo padronizado adotado por SEFAZ:

[1] Reserva de Número
[2] Pré-emissão (gravação da intenção)
[3] Montagem do XML
[4] Assinatura A1
[5] Envio SEFAZ (Mock, Homolog ou Produção)
[6] Tratamento da resposta (Autorizada, Rejeitada, Erro)
[7] Persistência do Documento (NfceDocumento)
[8] Auditoria


O backend já implementa **[1] e [2]**, e parte de **[5] via mock**.
Os próximos passos serão implementar **client SEFAZ real por UF** e o registro completo (**[7]** e **[8]**).

---

# 5. Reserva de Número (Service + Regra Fiscal)

### Regras principais:

- A numeração é **por filial + terminal + série**.
- A numeração deve ser sequencial e crescente.
- Cada reserva é **idempotente por `request_id`**.
- A reserva NÃO emite NFC-e — apenas bloqueia o número.

### Modelo utilizado:
- `NfceNumeroReserva`
  - `filial_id`
  - `terminal_id`
  - `serie`
  - `numero`
  - `request_id`

### Validações:

1. O usuário deve ter acesso autorizado à filial.
2. A filial deve estar **ativa**.
3. A filial deve ter série configurada.
4. O terminal deve estar ativo.
5. Não pode existir outro `request_id` para o mesmo contexto.

> Logs obrigatórios: `nfce_reserva_numero`
> Auditoria: opcional no MVP (registrada na emissão)

---

# 6. Pré-emissão

A pré-emissão grava a **intenção** de emitir NFC-e, antes de montar o XML.

### Regra principal

A pré-emissão deve ser:

- Persistida antes da emissão.
- Idempotente por `request_id`.
- Permitida somente se o número tiver sido reservado.

### Entidade:

- `NfcePreEmissao`
  - `filial_id`
  - `terminal_id`
  - `numero`
  - `serie`
  - `payload` (conteúdo completo da venda)
  - `request_id`

### Validações:

1. Número reservado deve existir.
2. Filial deve estar ativa.
3. Terminal deve estar ativo.
4. Filial deve ter certificado válido (`a1_expires_at`).
5. Ambiente do tenant/filial deve permitir emissão (mock, homolog, prod).

> Logs obrigatórios: `nfce_pre_emissao`
> Auditoria: **não obrigatória** (deixar apenas para emissão oficial)

---

# 7. Emissão NFC-e (MOCK / HOMOLOG / PRODUÇÃO)

A emissão é feita via `NfceEmissaoService`.
Ela recebe:

- `request_id`
- `user`
- `filial`
- `terminal`
- `client SEFAZ` (mock ou real)

---

# 8. Arquitetura de Emissão — *SEFAZ Clients* por UF

O sistema usa uma abstração:



BaseSefazClient (assinar/enviar XML)
└── SefazClientSP
└── SefazClientMG
└── SefazClientRJ
└── SefazClientES
└── SefazClientMock


Escolha feita por:

- `filial.uf`
- `filial.nfce_ambiente`

Usar o factory:



client = get_sefaz_client(uf, ambiente, filial)


### Motivos para usar clients específicos por UF:

- Cada UF pode usar webservice diferente.
- Cada UF tem particularidades de schema, endpoints ou comportamento.
- Facilita manutenção e testes.
- Evita “código Frankenstein” cheio de if/else por UF.

---

# 9. Regras por Ambiente

### 9.1 MOCK (dev/QA)

- XML não é enviado à SEFAZ.
- Chave pode ser gerada internamente (UUID → estrutura 44 dígitos simulada).
- Permite testar emissão sem certificado real.
- Permite testar rejeições simuladas.

### Logs obrigatórios:

- `nfce_emissao_mock_sucesso`
- `nfce_emissao_mock_erro`

### Auditoria:

- Em dev → opcional
- Em QA → recomendada para trilha completa

---

### 9.2 HOMOLOGAÇÃO

- Uso do certificado A1 válido.
- Ambiente SEFAZ homolog deve estar ativo por filial.
- Aceitar rejeições reais (testes de schema, erros de layout, etc.)
- Gravar auditoria.

### Logs obrigatórios:

- `nfce_emissao_sefaz_sucesso`
- `nfce_emissao_sefaz_rejeitada`
- `nfce_emissao_sefaz_erro`

### Auditoria: **OBRIGATÓRIA**

---

### 9.3 PRODUÇÃO

Regras:

- Certificado A1 deve estar válido (`a1_expires_at`).
- CSC deve ser válido.
- Filial deve estar configurada manualmente por time de implantação.
- Auditoria completa é obrigatória.

### Logs obrigatórios:

Mesmos de homologação.

### Auditoria obrigatória:

- Emissão
- Cancelamento
- Inutilização

---

# 10. Regras de Validação Fiscal (alto nível)

As validações principais (execução na pré-emissão/emissão ou no client SEFAZ) incluídas no MVP:

### 10.1. Validações de Filial

- UF deve ser válida (SP/MG/RJ/ES).
- Certificado não pode estar vencido.
- Ambiente deve ser permitido.
- CSC deve estar configurado (produção).
- IE válida (quando aplicável).

### 10.2. Validações de Terminal

- Terminal ativo.
- Terminal associado à filial.

### 10.3. Validações de Produtos (via payload da pré-emissão)

- CFOP válido para contexto (UF x operação).
- NCM válido.
- Alíquota ICMS deve estar coerente.
- Preço unitário, total e quantidade devem ser consistentes.

### 10.4. Validações de Número/Série

- Número deve ser sequencial.
- Série deve ser válida para a filial.
- Não pode ser reutilizado mesmo após erro (seguir idempotência por request).

---

# 11. Auditoria Fiscal

Cada evento relevante deve ser auditado:

| Evento | Auditoria | Log JSON | Observações |
|--------|-----------|----------|-------------|
| Emissão autorizada | ✔ obrigatória | ✔ | Armazenar: número, série, chave, protocolo |
| Emissão rejeitada | ✔ recomendada | ✔ | Gravar motivo e código |
| Cancelamento | ✔ obrigatória | ✔ | Quando implementado |
| Inutilização | ✔ obrigatória | ✔ | Quando implementado |
| Pré-emissão | opcional | ✔ | Auditoria pode ocorrer em emissão |

Mais detalhes em:
**`docs/fiscal/auditoria_nfce.md`**

---

# 12. Logs e Rastreabilidade

Devem ser emitidos no padrão definido em:
`docs/observabilidade/padroes_logs_backend.md`

Eventos fiscais obrigatórios estão em:
`docs/observabilidade/logbook_eventos.md`

---

# 13. Erros e Códigos de Resposta

Erros fiscais devem ser padronizados:

- `FISCAL_4xxx` → erros de negócio fiscal
- `FISCAL_5xxx` → erros de integração SEFAZ

Documentação detalhada em:
`docs/api/guia_erros_excecoes.md`

---

# 14. Evolução do Módulo Fiscal

Após o MVP, serão adicionados:

- Cancelamento
- Inutilização
- Contingência Offline (EPEC / FS-DA)
- Gerenciamento de CSCs
- Regra completa de ICMS por UF
- Impressão DANFE
- Relatórios fiscais

Cada evolução atualizará este documento conforme necessário.
