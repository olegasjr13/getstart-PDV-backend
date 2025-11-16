# Modelo de XML da NFC-e — GetStart PDV  
**Modelo 65 / Layout 4.00 + Regras Tributárias Atualizadas**

## 1. Objetivo

Este documento define o **modelo de XML da NFC-e** utilizado no GetStart PDV, incluindo:

- Estrutura principal do XML da NFC-e **Modelo 65 / Layout 4.00**.  
- Mapeamento dos campos entre **banco de dados / payload de venda** e o XML.  
- Como são aplicadas as **regras tributárias** (CFOP, NCM, CST/CSOSN, alíquotas, base de cálculo).  
- Diferenças por UF (SP, MG, RJ, ES) quando relevantes.  
- Pontos de atenção para **cancelamento, inutilização, contingência** e EPEC.  

Este documento não substitui os **manuais oficiais da SEFAZ**, mas consolida o **padrão interno** adotado pelo GetStart PDV.

---

## 2. Visão Geral do XML NFC-e 4.00 (Modelo 65)

A estrutura geral segue o layout oficial 4.00:

```xml
<NFe xmlns="http://www.portalfiscal.inf.br/nfe">
  <infNFe Id="NFe3519...44" versao="4.00">
    <ide>...</ide>
    <emit>...</emit>
    <dest>...</dest> <!-- opcional em certas operações -->
    <det nItem="1">...</det>
    <det nItem="2">...</det>
    ...
    <total>...</total>
    <transp>...</transp>
    <pag>...</pag>
    <infAdic>...</infAdic>
  </infNFe>
</NFe>
```

Blocos principais:

- `<ide>` → identificação da NFC-e (UF, série, número, modelo, tpEmis, etc.).  
- `<emit>` → dados do emitente (filial).  
- `<dest>` → dados do destinatário (quando informado).  
- `<det>` → itens da venda (+ impostos).  
- `<total>` → totalizadores da NF.  
- `<pag>` → informações de pagamento.  
- `<infAdic>` → campos livres (observações fiscais e internas).

---

## 3. Mapeamento de Campos — Bloco `<ide>`

O bloco `<ide>` identifica a NFC-e:

Campos principais:

- `cUF` → Código da UF (ex.: 35 SP, 31 MG, 33 RJ, 32 ES).  
- `cNF` → Código numérico aleatório (8 dígitos).  
- `natOp` → Natureza da operação (ex.: "VENDA AO CONSUMIDOR").  
- `mod` → Modelo do documento (sempre `65` para NFC-e).  
- `serie` → Série definida na filial.  
- `nNF` → Número da NFC-e (reserva/controle interno).  
- `dhEmi` → Data/hora de emissão.  
- `tpNF` → Tipo de operação (1-saída, 0-entrada).  
- `idDest` → Local de destino (1-interna, 2-interestadual).  
- `cMunFG` → Código do município de ocorrência do fato gerador.  
- `tpImp` → Formato DANFE (sempre 4 – NFC-e).  
- `tpEmis` → Tipo de emissão (1-normal, 9-contingência offline, etc.).  
- `tpAmb` → Ambiente (1-produção, 2-homologação).  
- `finNFe` → Finalidade (1-normal).  
- `indFinal` → Consumidor final (1-sim).  
- `indPres` → Indicador de presença (1-operação presencial).  
- `procEmi` / `verProc` → Identificação do sistema emissor (GetStart PDV).

### 3.1. De onde vem essas informações?

- `cUF`, `cMunFG`, `tpAmb` → da **Filial** (UF, município, ambiente NFC-e).  
- `serie`, `nNF` → de `NfceNumeroReserva` / controle interno.  
- `dhEmi` → timestamp da pré-emissão/emissão.  
- `natOp` → da **configuração do CFOP/operacão** (ver seção de regras tributárias).  
- `indFinal`, `indPres` → sempre configurados para venda varejo presencial.  

---

## 4. Bloco `<emit>` — Emitente (Filial)

Exemplo:

```xml
<emit>
  <CNPJ>12345678000199</CNPJ>
  <xNome>GETSTART LOJA TESTE LTDA</xNome>
  <xFant>GETSTART LOJA</xFant>
  <enderEmit>
    <xLgr>Rua Exemplo</xLgr>
    <nro>123</nro>
    <xBairro>Centro</xBairro>
    <cMun>3550308</cMun>
    <xMun>SAO PAULO</xMun>
    <UF>SP</UF>
    <CEP>01000000</CEP>
    <cPais>1058</cPais>
    <xPais>BRASIL</xPais>
    <fone>1133334444</fone>
  </enderEmit>
  <IE>123456789000</IE>
  <CRT>1</CRT>
</emit>
```

### 4.1. Mapeamento

- Todos os dados vêm da **Filial** (CNPJ, razão social, fantasia, endereço, IE).  
- `CRT` → Código de Regime Tributário:  
  - 1 → Simples Nacional  
  - 2 → Simples Nacional – excesso  
  - 3 → Regime Normal  

> **Impacto nas regras tributárias**:  
> O `CRT` definirá **quais tipos de CST/CSOSN e grupos ICMS** serão usados no item (ICMS00, ICMS40, ICMSSN102, etc.).

---

## 5. Bloco `<dest>` — Destinatário

Para NFC-e:

- Em vendas comuns, pode ser não informado (consumidor não identificado).  
- Quando o cliente informa CPF/CNPJ → preencher `<dest>`.

Exemplo CPF:

```xml
<dest>
  <CPF>12345678909</CPF>
  <indIEDest>9</indIEDest>
</dest>
```

Mapeamento:

- Vem do payload de venda (`cliente` opcional).  
- `indIEDest` geralmente é `9` (não contribuinte) para varejo.

---

## 6. Blocos `<det>` — Itens + Impostos (Regras Tributárias)

Cada `<det>` representa um item:

```xml
<det nItem="1">
  <prod>...</prod>
  <imposto>...</imposto>
</det>
```

### 6.1. `<prod>` — Dados Comerciais

Campos principais:

- `cProd` → Código interno do produto.  
- `cEAN` → EAN se existir (ou "SEM GTIN").  
- `xProd` → Descrição do produto.  
- `NCM` → NCM do produto (obrigatório).  
- `CFOP` → Código fiscal da operação.  
- `uCom` → Unidade comercial.  
- `qCom` → Quantidade.  
- `vUnCom` → Valor unitário.  
- `vProd` → Total (qCom * vUnCom).  
- `cEANTrib`, `uTrib`, `qTrib`, `vUnTrib` → geralmente iguais a comercial no varejo.  
- `indTot` → se compõe o total (1-sim).

### 6.2. Mapeamento dos dados do produto

Todos estes dados são alimentados a partir de:

- Tabela de **Produtos** (NCM, unidade, descrição, EAN).  
- Tabela de **Configuração Fiscal do Produto** (CFOP padrão, CST/CSOSN, alíquotas).  
- Payload de venda (quantidade, valor unitário, descontos).  

---

## 7. Regras Tributárias — ICMS (Atualizadas)

O bloco `<imposto>` para ICMS varia conforme:

- UF da filial  
- Regime tributário (`CRT`)  
- Tipo de operação (dentro do estado, fora do estado, contribuinte/não-contribuinte)  
- Configuração fiscal do produto (CST/CSOSN, alíquota)

### 7.1. Simples Nacional (`CRT = 1` ou `2`)

Neste caso, a NFC-e usa grupos **CSOSN** (ex.: 102, 103, 400, 500).

Exemplo Simples Nacional – CSOSN 102:

```xml
<ICMS>
  <ICMSSN102>
    <orig>0</orig>
    <CSOSN>102</CSOSN>
  </ICMSSN102>
</ICMS>
```

Regras internas (GetStart PDV):

- Para produtos sem destaque de ICMS no documento (Simples Nacional comum):
  - Usar **CSOSN 102** ou **103** (conforme tabela fiscal).  
- Caso exista substituição tributária ou outra particularidade:
  - Usar CSOSN apropriado (201, 202, 500, etc.), conforme mapeamento da **tabela de regras fiscais** (que virá do seed CFOP/NCM ou cadastro fiscal).

### 7.2. Regime Normal (`CRT = 3`)

Usam-se os grupos **CST** (00, 20, 40, 41, 60, etc.).

Exemplo tributação integral (CST 00):

```xml
<ICMS>
  <ICMS00>
    <orig>0</orig>
    <CST>00</CST>
    <modBC>3</modBC>
    <vBC>100.00</vBC>
    <pICMS>18.00</pICMS>
    <vICMS>18.00</vICMS>
  </ICMS00>
</ICMS>
```

Regras:

- A partir do cadastro fiscal do produto, para aquele CFOP/UF:
  - CST 00 → tributado integral  
  - CST 20 → com redução de base  
  - CST 40/41 → isento/sem incidência  
- `modBC`, `pICMS`, `vBC`, `vICMS` calculados com base nas alíquotas configuradas para a UF da filial.

### 7.3. Origem (`orig`)

`orig` indica origem da mercadoria:

- 0 — Nacional  
- 1 — Estrangeira – importação direta  
- 2 — Estrangeira – adquirida no mercado interno  
- etc.

Configurado na ficha do produto.

---

## 8. Regras Tributárias — PIS/COFINS

### 8.1. Simples Nacional

Em muitos casos no Simples, PIS/COFINS não são destacados na NFC-e, usando códigos de **não incidência**.

Exemplo:

```xml
<PIS>
  <PISOutr>
    <CST>49</CST>
    <vBC>0.00</vBC>
    <pPIS>0.00</pPIS>
    <vPIS>0.00</vPIS>
  </PISOutr>
</PIS>
<COFINS>
  <COFINSOutr>
    <CST>49</CST>
    <vBC>0.00</vBC>
    <pCOFINS>0.00</pCOFINS>
    <vCOFINS>0.00</vCOFINS>
  </COFINSOutr>
</COFINS>
```

### 8.2. Regime Normal

Quando a empresa está no regime normal e deseja destacar PIS/COFINS:

- Usar grupos `PISAliq` / `COFINSAliq` (CST 01 ou 02).  
- Alíquotas configuradas por produto ou NCM.

Regras internas:

- A tabela de **parâmetros fiscais** mapeia CFOP/NCM + regime + UF → CST e alíquotas.  
- Seed `cfop_ncm_seed` deve iniciar uma massa mínima coerente com o varejo.

---

## 9. Regras Tributárias — CFOP

CFOP define a **natureza da operação**.

### 9.1. Regra geral no varejo interno (dentro da UF)

- CFOP padrão de venda varejo:  
  - **5.102** – Venda de mercadoria adquirida ou recebida de terceiros.  
- Caso interestadual (filial vendendo para outra UF – pouco comum em NFC-e):  
  - **6.102**.

### 9.2. Mapeamento interno

O GetStart PDV deve ter:

- Tabela de **Operações Fiscais** (ex.: VENDA_INTERNA, VENDA_INTERESTADUAL, DEVOLUCAO_CONSUMIDOR).  
- Cada operação mapeia o CFOP padrão, que pode ser ajustado por UF.

No XML:

- CFOP é preenchido em `<CFOP>` de `<prod>` para cada item.

---

## 10. Bloco `<total>` — Totais

Exemplo simplificado:

```xml
<total>
  <ICMSTot>
    <vBC>100.00</vBC>
    <vICMS>18.00</vICMS>
    <vICMSDeson>0.00</vICMSDeson>
    <vFCP>0.00</vFCP>
    <vBCST>0.00</vBCST>
    <vST>0.00</vST>
    <vProd>100.00</vProd>
    <vFrete>0.00</vFrete>
    <vSeg>0.00</vSeg>
    <vDesc>0.00</vDesc>
    <vII>0.00</vII>
    <vIPI>0.00</vIPI>
    <vPIS>0.00</vPIS>
    <vCOFINS>0.00</vCOFINS>
    <vOutro>0.00</vOutro>
    <vNF>100.00</vNF>
  </ICMSTot>
</total>
```

### 10.1. Mapeamento / Regras

- `vProd` → soma de todos os `vProd` dos itens.  
- `vDesc` → soma de descontos.  
- `vNF` → valor final da NFC-e.  
- `vBC`, `vICMS`, `vPIS`, `vCOFINS` → somatório dos itens.  

As novas **regras tributárias** influenciam diretamente:

- `vBC` e `vICMS` (para CST 00, 20 etc.).  
- `vPIS` / `vCOFINS` (quando destacadas).  

---

## 11. Bloco `<pag>` — Pagamento

Exemplo:

```xml
<pag>
  <detPag>
    <tPag>01</tPag> <!-- dinheiro -->
    <vPag>50.00</vPag>
  </detPag>
  <detPag>
    <tPag>03</tPag> <!-- cartão de crédito -->
    <vPag>50.00</vPag>
  </detPag>
  <vTroco>0.00</vTroco>
</pag>
```

### 11.1. Mapeamento

- Vem da **tela de pagamento do PDV**.  
- Pode ter múltiplos meios (dinheiro, cartão, pix, etc.).  
- Deve fechar exatamente o `vNF`.

---

## 12. Bloco `<infAdic>` — Informações Adicionais

Usado para:

- Informações fiscais adicionais (ex.: FCP, benefícios, legislação específica).  
- Mensagens internas (limitadas pela legislação).  

Regras:

- Não inserir dados sensíveis (cartão, CPF não permitido, etc.).  
- Não usar para alterar sentido fiscal (apenas informar).

---

## 13. XML de Cancelamento (Resumo)

Conectado ao doc `cancelamento_nfce.md`:

- Usa **evento 110111** no layout 4.00.  
- Liga a NFC-e original (pela chave) ao evento.  

---

## 14. XML de Inutilização (Resumo)

Conectado ao doc `inutilizacao_nfce.md`:

- Usa `<inutNFe>` / `<infInut>` com `mod=65`.  
- Informa série, faixa de numeração e justificativa.

---

## 15. Efeitos das “Novas Regras Tributárias” neste documento

Com base nas definições recentes que adotamos:

1. **Obrigatoriedade de CFOP/NCM reais**  
   - Todos os produtos usados nos testes devem ter NCM válido.  
   - O seed `cfop_ncm_seed` deve prover uma base mínima coerente para SP, MG, RJ, ES.  
   - O XML sempre terá `<NCM>` preenchido corretamente.

2. **Separação por Regime Tributário (CRT)**  
   - Se `CRT=1` ou `2` → usar grupos `ICMSSNxxx`, com CSOSN adequados.  
   - Se `CRT=3` → usar grupos `ICMSxx` (CST), com alíquota e base de cálculo.  

3. **Tratamento de PIS/COFINS**  
   - Para Simples Nacional → usar CST 49 (ou equivalente) sem destaque, quando aplicável.  
   - Para Regime Normal → destacar PIS/COFINS quando configurado.

4. **CFOP vinculado à operação**  
   - A operação de venda varejo interna deve usar CFOPs `5.102`/`5.405` etc., conforme o tipo de produto.  
   - O sistema deve permitir parametrização por UF, mas o XML sempre refletirá o CFOP resolvido na operação.

5. **Validação pré-XML**  
   - Antes de montar o XML, o backend valida:  
     - Produto tem NCM  
     - Produto tem CFOP compatível com a operação  
     - CST/CSOSN configurado para a combinação (UF, CFOP, NCM, regime)  
   - Se qualquer dado fiscal estiver faltando → erro `FISCAL_4007` (ou similar) antes de chamar SEFAZ.

---

## 16. Resumo

Este documento consolida:

- A estrutura do XML NFC-e 4.00 (Modelo 65)  
- O mapeamento entre dados de negócio (produto, venda, filial, cliente) e o XML  
- A aplicação das **novas regras tributárias** (CFOP, NCM, CST/CSOSN, alíquotas)  
- O vínculo com cancelamento, inutilização e contingência  

A implementação do XML deve seguir este modelo como padrão de referência, em conjunto com os demais documentos fiscais do projeto.
