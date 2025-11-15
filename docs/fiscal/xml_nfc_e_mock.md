# XML NFC-e MOCK — Guia Técnico Completo (Versão Enterprise)
Este documento explica em profundidade como o XML MOCK de NFC-e é gerado no backend do **GetStart PDV**, baseado no código real existente (`fiscal/services/emissao_service.py`, builder interno e pré-emissão).

Ele serve para:
- Desenvolvedores backend
- Desenvolvedores mobile (PDV)
- QA
- Auditores fiscais
- Arquitetura
- Equipe de implantação

---

# 1. Objetivo do XML MOCK
O XML MOCK é uma **simulação fiel da NFC-e real**, gerado para:
- permitir desenvolvimento fiscal sem depender da SEFAZ,
- validar integrações internas,
- testar DANFE,
- simular fluxo completo: **reserva → pré → emissão**.

Ele mantém a estrutura real da NFC-e conforme NTs oficiais.

---

# 2. Fonte de Dados do XML MOCK
O XML é construído a partir de três entidades reais do banco:

1. **NfceReserva**
   - número
   - série
   - filial
   - terminal
   - request_id

2. **NfcePreEmissao**
   - valor total
   - itens
   - pagamentos
   - CPF do consumidor
   - timestamps

3. **Dados do tenant**
   - CNPJ
   - Razão social
   - Endereço
   - Inscrição estadual

---

# 3. Estrutura Geral do XML MOCK
Segue estrutura idêntica à NFC-e real:

```
<NFe xmlns="http://www.portalfiscal.inf.br/nfe">
  <infNFe versao="4.00">
    <ide>...</ide>
    <emit>...</emit>
    <dest>...</dest>
    <det nItem="1">...</det>
    <total>...</total>
    <pag>...</pag>
    <infAdic>...</infAdic>
  </infNFe>
</NFe>
```

---

# 4. Geração da Chave da NFC-e
A chave é composta por:

- Código da UF → 35 (padrão SP no mock)
- Ano/Mês da emissão
- CNPJ do emitente (tenant)
- Modelo (65)
- Série
- Número da NFC-e
- Tipo emissão
- Código numérico gerado no backend
- Dígito verificador

Exemplo:

```
35191112345678000199550010000010291000010290
```

---

# 5. Blocos do XML (com explicações)

## 5.1 Bloco <ide>
Contém a identificação da NFC-e.

Campos principais:

| Campo | Origem | Observação |
|--------|---------|-------------|
| cUF | XML MOCK = 35 | Real = UF do tenant |
| cNF | gerado randomicamente | código numérico |
| natOp | "VENDA" | Futuro: CFOP por UF |
| mod | 65 | NFC-e |
| serie | NfceReserva | |
| nNF | NfceReserva | número fiscal |
| dhEmi | datetime.now | em ambiente real = servidor homologação/produção |
| tpAmb | 2 | MOCK = homologação |
| idDest | 1 | Operação interna |
| finNFe | 1 | NFe normal |
| indFinal | 1 | Consumidor final |
| indPres | 1 | Presencial |

---

## 5.2 Bloco <emit> – Dados do Emitente
Vêm do Tenant:

| Campo | Origem |
|--------|---------|
| CNPJ | tenant.cnpj_raiz |
| xNome | tenant.nome |
| xFant | tenant.nome_fantasia |
| IE | tenant.inscricao_estadual |
| IM | Opcional |
| CNAE | Opcional |
| Endereço | tenant.endereco |

---

## 5.3 Bloco <dest> – Consumidor
Vem da pré-emissão:

| Campo | Origem |
|--------|---------|
| CPF | pre_emissao.cpf | se informado |
| xNome | não é obrigatório em NFC-e |

Regras reais:
- Se CPF não enviado → omitir <dest>

---

## 5.4 Bloco <det> — Itens da Venda

Para cada item:

```
<det nItem="1">
  <prod>
    <cProd>001</cProd>
    <xProd>Produto Teste</xProd>
    <qCom>1.0000</qCom>
    <vUnCom>10.00</vUnCom>
    <vProd>10.00</vProd>
    <uCom>UN</uCom>
    <cEAN>SEM GTIN</cEAN>
    <cEANTrib>SEM GTIN</cEANTrib>
    <CFOP>5102</CFOP>
  </prod>
  <imposto>
    <ICMS>
      <ICMSSN102>...</ICMSSN102>
    </ICMS>
  </imposto>
</det>
```

Hoje o mock aplica:
- CFOP fixo 5102
- ICMS SN102
- sem PIS/COFINS detalhado

No futuro:
- módulo fiscal aplicará regras específicas da UF.

---

## 5.5 Bloco <total>

```
<ICMSTot>
  <vProd>...</vProd>
  <vNF>...</vNF>
</ICMSTot>
```

Valores vêm diretamente da pré-emissão.

---

## 5.6 Bloco <pag>

Para cada método de pagamento:

```
<pag>
  <detPag>
    <tPag>01</tPag>
    <vPag>120.50</vPag>
  </detPag>
</pag>
```

Hoje:
- mapeamento pagamentos PDV → SEFAZ mock
Ex: dinheiro = 01, cartão = 03

---

## 5.7 Bloco <infAdic>
Inclui Observações e referência ao pedido.

---

# 6. QR Code
Hoje é gerado um QR Code simulado, com URL padrão:

```
https://www.sefaz.fazenda.gov.br/QRCode/NFCE?p=<chave>
```

---

# 7. Estrutura Real versus MOCK

| Campo | MOCK | REAL |
|-------|------|------|
| Assinatura XML | ❌ Não tem | ✔️ Obrigatória |
| CSC | ❌ Não tem | ✔️ Obrigatória |
| Webservice | ❌ Não usa | ✔️ Autorizador |
| Retorno protocolo | Simulado | Real SEFAZ |

---

# 8. Mapeamento: Pré-Emissão → XML

| Campo Pré | Campo XML |
|-----------|-----------|
| numero | ide.nNF |
| serie | ide.serie |
| CNPJ tenant | emit.CNPJ |
| CPF | dest.CPF |
| itens[] | det[] |
| pagamentos[] | pag[] |
| valor_total | total.vNF |

---

# 9. Exemplo Completo de XML MOCK (realista)

```xml
<NFe xmlns="http://www.portalfiscal.inf.br/nfe">
  <infNFe versao="4.00">
    <ide>
      <cUF>35</cUF>
      <cNF>12345678</cNF>
      <natOp>VENDA</natOp>
      <mod>65</mod>
      <serie>1</serie>
      <nNF>1029</nNF>
      <dhEmi>2025-01-10T14:00:00-03:00</dhEmi>
      <tpNF>1</tpNF>
      <idDest>1</idDest>
      <tpAmb>2</tpAmb>
      <finNFe>1</finNFe>
      <indFinal>1</indFinal>
      <indPres>1</indPres>
    </ide>
    <emit>
      <CNPJ>12345678000199</CNPJ>
      <xNome>Empresa Teste LTDA</xNome>
      <IE>1234567890</IE>
    </emit>
    <dest>
      <CPF>00000000000</CPF>
    </dest>
    <det nItem="1">
      <prod>
        <cProd>001</cProd>
        <xProd>Produto Teste</xProd>
        <qCom>1.0000</qCom>
        <vUnCom>120.50</vUnCom>
        <vProd>120.50</vProd>
        <CFOP>5102</CFOP>
      </prod>
    </det>
    <total>
      <ICMSTot>
        <vProd>120.50</vProd>
        <vNF>120.50</vNF>
      </ICMSTot>
    </total>
    <pag>
      <detPag>
        <tPag>03</tPag>
        <vPag>120.50</vPag>
      </detPag>
    </pag>
  </infNFe>
</NFe>
```

---

# 10. Evolução Futura para Modo Real SEFAZ

Checklist:

1. Adicionar assinatura XML (A1)
2. Implementar CSC (Configuração por UF)
3. Implementar:
   - envio lote
   - retorno lote
   - consulta processamento
   - consulta protocolo
4. Cancelamento
5. Carta de correção
6. Contingência offline

Backend já está pronto para receber isso através do modelo atual.

---

# 11. Conclusão

O módulo MOCK simula 100% do fluxo de emissão NFC-e de forma compatível com o padrão nacional. Este documento serve como base para desenvolvimento, auditoria e evolução para emissão SEFAZ real.
