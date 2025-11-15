# Guia de Migração — Modo Mock → Emissão Real SEFAZ (NFC-e)

## 1. Objetivo

Orientar **passo a passo** a migração da emissão NFC-e:

- De modo **mock/simulado** (sem comunicação com SEFAZ)
- Para modo **real**, com transmissão oficial para SEFAZ (por UF)

---

## 2. Situação Atual (Mock)

No modo mock:

- XML é gerado localmente.
- Não há envio para SEFAZ.
- Protocolo de autorização é simulado.
- Chave de acesso é gerada de forma válida, mas não registrada na SEFAZ.
- O objetivo é:
  - Validar frontend/PDV.
  - Validar regras internas.
  - Testar fluxos de loja.

---

## 3. Pré-requisitos para Emissão Real

### 3.1 Por UF

Cada UF tem:

- URL própria de webservices NFe/NFC-e.
- Requisitos de:
  - CSC.
  - Cadastro do contribuinte.
  - Configuração de ambiente (`homologação` vs `produção`).

### 3.2 Checklist por Filial

Para cada Filial que fará emissão real:

- [ ] CNPJ com inscrição estadual ativa na UF.
- [ ] Certificado A1 válido e instalado (campo `a1_pfx` + `a1_expires_at`).
- [ ] CSC (Código de Segurança do Contribuinte) configurado:
  - `csc_id`
  - `csc_token`
- [ ] Ambiente da Filial configurado:
  - `ambiente = homologacao` para testes.
  - `ambiente = producao` após homologação.

---

## 4. Alterações Técnicas Necessárias

### 4.1 Módulo de Emissão

Substituir o “mock engine” por engine real:

- Mock:
  - Gera XML e protocolo fake.
  - Não chama SEFAZ.

- Real:
  1. Gera XML conforme layout oficial.
  2. Assina com A1.
  3. Transmite para SEFAZ via webservice.
  4. Interpreta retorno:
     - `Autorizado`
     - `Rejeitado`
     - `Em processamento`, etc.

### 4.2 Tratamento de Erros SEFAZ

- Rejeição deve resultar em:
  - Status de NFC-e `REJEITADA`.
  - Registro de:
    - Código de erro SEFAZ.
    - Mensagem de erro.
- Responsabilidade:
  - Backend:
    - Mapeia códigos SEFAZ para mensagens internas.
  - PDV:
    - Exibe mensagem amigável.
    - Decide se permite nova tentativa (com ajuste de dados).

---

## 5. Fases de Migração

### 5.1 Fase 1 — Homologação Técnica

- Configurar algumas Filiais em `ambiente = homologacao`.
- Manter modo mock ativável por config (feature flag).
- Executar:
  - Emissão de NFC-e de teste.
  - Cancelamentos.
  - Testes de contingência (se aplicável na UF).

### 5.2 Fase 2 — Piloto Controlado

- Selecionar poucas Filiais reais.
- Subir ambiente `producao`:
  - Com volume controlado.
- Monitorar:
  - Tempo de resposta SEFAZ.
  - Erros de comunicação.
  - Logs de rejeição.

### 5.3 Fase 3 — Rollout Gradual

- Habilitar emissão real para mais Filiais:
  - Por UF e região.
- Desativar modo mock:
  - Para tenants que migrarem completamente.

---

## 6. Configuração por Ambiente

### 6.1 Parâmetros

Em nível de configuração (por UF ou global):

- URLs de:
  - Autorização NFC-e.
  - Consulta situação.
  - Inutilização (quando suportado).
- Timeouts de conexão.
- Retries.

### 6.2 Feature Flags

Sugestão de flags por Filial ou Tenant:

- `NFCE_USE_MOCK = true|false`
- `NFCE_ENV = ["homologacao", "producao"]`
- `NFCE_ENABLE_CANCELAMENTO = true|false`

---

## 7. Testes Obrigatórios de Migração

### 7.1 Emissão

- Emissão com:
  - Sem CPF.
  - Com CPF.
  - Várias formas de pagamento.
  - Vários itens.

### 7.2 Cancelamento

- Cancelar dentro da janela de tempo permitida pela UF.
- Verificar se:
  - Status retorna como `CANCELADA`.
  - Protocolo de cancelamento é armazenado.

### 7.3 Falhas de comunicação

- Simular:
  - Timeout.
  - Webservice indisponível.
- Backend deve:
  - Retornar erro claro.
  - Não marcar NFC-e como autorizada sem resposta.

---

## 8. Monitoramento em Produção

- Métricas:
  - Quantidade de NFC-e autorizadas por período.
  - Taxa de rejeição por UF.
  - Latência de autorização.
- Alertas:
  - Erros contínuos de comunicação com SEFAZ.
  - Aumento súbito de rejeições com o mesmo código.

---

## 9. Checklist Final de Migração

- [ ] Módulo de emissão real implementado e testado.
- [ ] Configuração de A1 + CSC testada em homologação.
- [ ] Logs fiscais e de auditoria funcionando.
- [ ] Piloto em produção validado.
- [ ] Documentação atualizada (`regras_fiscais`, `xml_nfc_e_mock`, este guia).

---
