
---

## 2️⃣ `fiscal/guia_danfe_nfce.md` — Guia DANFE NFC-e

```markdown
# Guia do DANFE NFC-e — GetStart PDV

## 1. Objetivo

Definir como o DANFE NFC-e (Documento Auxiliar da Nota Fiscal de Consumidor Eletrônica) é:

- Gerado
- Preenchido
- Exibido/imprimido no PDV

E como ele se relaciona com:

- XML da NFC-e
- Backend
- Aplicativo PDV

---

## 2. Papel do DANFE NFC-e

- É **representação gráfica** da NFC-e:
  - Mostra dados principais da operação.
  - Fornece QRCode de consulta na SEFAZ.
- Pode ser:
  - Impresso em papel térmico (reduzido).
  - Exibido em tela (PDV mobile).
  - Enviado digitalmente (PDF) em alguns casos.

---

## 3. Estrutura Lógica do DANFE

### 3.1 Blocos principais

1. **Cabeçalho**
   - Nome/razão social da empresa.
   - CNPJ/IE.
   - Endereço.
   - Identificação NFC-e:
     - Número, série, data/hora.

2. **Dados da venda**
   - Itens vendidos (descrição, quantidade, unidade, valor unitário, valor subtotal).
   - Totais:
     - Total bruto.
     - Descontos.
     - Acréscimos.
     - Total NFC-e.

3. **Pagamentos**
   - Forma de pagamento (DINHEIRO, CRÉDITO, DÉBITO, PIX, etc.).
   - Valor pago.
   - Troco (quando houver).

4. **QRCode**
   - Código bidimensional para consulta da NFC-e na SEFAZ.
   - Em modo mock:
     - Pode apontar para uma URL de ambiente de desenvolvimento ou um placeholder.

5. **Informações adicionais**
   - Mensagens fiscais obrigatórias (ex.: termos do Simples Nacional).
   - Mensagens comerciais opcionais (ex.: “Volte sempre”).

---

## 4. Mapeamento XML NFC-e → DANFE

Exemplo simplificado de mapeamento:

| XML                             | DANFE                                     |
|---------------------------------|-------------------------------------------|
| `ide.nNF`                       | Número da NFC-e                          |
| `ide.serie`                    | Série                                    |
| `ide.dhEmi`                    | Data/Hora de emissão                     |
| `emit.xNome`                   | Razão social                             |
| `emit.CNPJ`                    | CNPJ                                     |
| `emit.enderEmit.xLgr`          | Endereço (logradouro)                    |
| `det[x].prod.xProd`            | Descrição do item                        |
| `det[x].prod.qCom`             | Quantidade                               |
| `det[x].prod.vUnCom`           | Valor unitário                           |
| `det[x].prod.vProd`            | Subtotal do item                         |
| `total.ICMSTot.vNF`            | Valor total da NFC-e                     |
| `pag.detPag.tPag`              | Forma de pagamento                       |
| `pag.detPag.vPag`              | Valor pago                               |
| `infNFeSupl.qrCode`            | QRCode impresso                          |

---

## 5. Responsabilidades (Backend vs PDV)

### 5.1 Backend

- Gera XML com estrutura correta.
- Gera `chave` e `qrCode` (quando modo real).
- Pode gerar DANFE como:
  - PDF (binary → `base64`).
  - HTML (template) — se essa for a estratégia adotada.
- Garante que:
  - Dados fiscais estejam corretos e consistentes.

### 5.2 PDV

Dependendo da estratégia definida:

1. **DANFE renderizado no backend**  
   - PDV recebe `danfe_base64` (PDF/PNG).
   - Exibe ou imprime via componente nativo.

2. **DANFE renderizado no PDV**  
   - PDV recebe apenas XML e:
     - Constrói layout localmente.
     - Gera QRCode a partir do campo `infNFeSupl.qrCode`.

> O projeto GetStart PDV deve **especificar uma estratégia oficial** e mantê-la consistente para todos os PDVs.

---

## 6. Cenários Especiais

### 6.1 Reimpressão

- É permitido reimprimir um DANFE já emitido.
- PDV deve chamar endpoint específico ou reutilizar dados armazenados localmente.
- Backend deve:
  - Registrar log de reimpressão (quando exigido para auditoria).

### 6.2 DANFE após cancelamento

- Após cancelamento, uma nova impressão:
  - Deve indicar que a NFC-e está cancelada.
  - Layout pode exibir “CANCELADA” em destaque.

---

## 7. Requisitos Fiscais Mínimos no DANFE

- QRCode legível.
- Dados do emitente (CNPJ, IE, nome, endereço).
- Número + série + data/hora.
- Valor total.
- Identificação mínima do destinatário (quando houver).
- Mensagens obrigatórias por regime tributário (ex.: Simples Nacional).

---

## 8. Sugestão de Layout

- Papel térmico 80mm:
  - Itens com quebras de linha ajustadas.
  - QRCode na parte inferior.
- Layout mobile:
  - Resumo de itens.
  - QRCode clicável/zoomável.

---

## 9. Testes recomendados

- Impressão com poucos itens vs muitos itens.
- Descontos e acréscimos.
- Pagamentos múltiplos.
- Cancelamento + reimpressão.
- Mudança de regime tributário → alteração de mensagens no rodapé.

---
