# GetStart PDV — Guia de Implantação Fiscal por UF (NFC-e)

> Atenção: este documento é um guia técnico-operacional. A validação final das regras fiscais deve ser feita com contador e legislação específica de cada UF.

## 1. Etapas Gerais de Implantação

1. Cadastro da empresa (Filial) no sistema:
   - CNPJ, IE, UF, regime tributário.
   - Cadastro ou importação do CSC (Código de Segurança do Contribuinte).
   - Upload do certificado A1 (PFX) e senha.

2. Configuração de ambiente:
   - Homologação primeiro (ambiente de testes).
   - Produção somente após validação com contador e emissão de testes.

3. Testes em homologação:
   - Emissão de NFC-e de teste.
   - Verificação de rejeições comuns (CFOP, CST, CSOSN, NCM).
   - Validação de layout do DANFE.

4. Passagem para produção:
   - Alterar `ambiente` da Filial para `producao`.
   - Garantir horário e data corretos no dispositivo.

---

## 2. Especificidades por UF (alto nível)

### 2.1 São Paulo (SP)

- Modelo: NFC-e (modelo 65).
- Necessário CSC (ID + token) para geração de QRCode.
- Regras específicas:
  - Campo `informação adicional` pode conter mensagem padronizada do contribuinte.
  - Certificado A1 deve estar válido (verificação diária).
- Recomendações:
  - Testar rejeições típicas:
    - NCM inválido.
    - CFOP incompatível com operação.
    - CST/CSOSN incompatível com regime.

### 2.2 Minas Gerais (MG)

- Modelo: NFC-e (modelo 65).
- Verificar com contador:
  - Obrigatoriedade de informar destinatário (CPF/CNPJ) acima de certo valor.
  - Regras de arredondamento se aplicáveis.

### 2.3 Paraná (PR), Rio de Janeiro (RJ) e demais

- Em geral:
  - Seguem especificações de NFC-e do ENCAT.
  - Podem possuir campos de uso específico da UF.

Diretriz:
- O backend deve ser construído para permitir parametrização por UF (tabela de configuração de UF) sem alterar código de regra geral.

---

## 3. Boas Práticas de Implantação

1. Sempre iniciar em homologação.
2. Emissão de pelo menos:
   - 1 NFC-e com pagamento em dinheiro.
   - 1 NFC-e com pagamento TEF.
   - 1 NFC-e com cancelamento.
3. Validar DANFE com o cliente e contador.
4. Habilitar logs de debug em ambiente de teste, nunca em produção.

---

## 4. Responsabilidades

- **Equipe Backend:** garantir aderência ao layout técnico, numeração, A1, CSC e integridade do XML.
- **Equipe Mobile/PDV:** seguir rigorosamente os fluxos de reserva, pré-emissão, emissão e cancelamento.
- **Contador/Consultoria Fiscal:** validar CFOP, CST, CSOSN, NCM, alíquotas e regimes.
