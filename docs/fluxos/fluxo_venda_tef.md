 
📄 FLUXO COMPLETO DE VENDA COM TEF (SINCRONO) – V1.0
🧩 1. Visão Geral

Este documento descreve o fluxo completo de uma operação de venda em um PDV no modelo TEF síncrono, amplamente utilizado em soluções como SiTef, TEF Dedicado/Discado, TEF IP, TEF Local.

O fluxo foi projetado para funcionar em ambiente multitenant, com:

Empresas → Filiais → Terminais

Métodos de Pagamento configurados por Filial

Regras TEF específicas por Filial ou por Terminal

API Fiscal externa (ex.: NDD, TecnoSpeed, API própria)

Carrinho de Venda

Emissão NFC-e/NF-e externamente

O fluxo segue a regra:

TEF → (se sucesso) → Emissão Fiscal → Impressão → Finalização da Venda

Caso qualquer etapa falhe, a venda não é finalizada.

🧩 2. Pré-Condições Necessárias
2.1. Cadastros Essenciais

Antes de iniciar uma venda, devem existir:

Cadastro	Descrição	Status
Empresa	Identificação do tenant	OK
Filial	CNPJ emissor, endereço, UF, regras fiscais	OK
FilialNFCeConfig	Configurações necessárias para emissão via API externa	OK
Terminal	Terminal físico (PDV), com configuração TEF local	OK
Métodos de Pagamento	(Dinheiro, PIX, Crédito, Débito, Voucher etc.)	OK
FilialMétodoPagamento	Quais métodos a filial aceita	OK
TefConfig	Configurações TEF padrão da filial ou específicas de terminal	OK
Produtos	NCM, preço, impostos	OK
🧩 3. Fluxo Completo da Venda
🟦 Passo 1 – Início da Venda e Criação do Carrinho

Usuário acessa o Terminal (PDV).

PDV cria uma instância de Venda com status "ABERTO".

Sistema grava:

filial_id

terminal_id

usuário operador

data/hora de abertura

Carrinho está vazio e pronto para produtos.

🟦 Passo 2 – Adição de Produtos ao Carrinho

Usuário pesquisa produto por:

código

descrição

código de barras

atalhos pré-configurados

Para cada produto:

PDV verifica se produto ativo

Se quantidade > estoque disponível → exibe erro

Calcula preço total item = preço * quantidade

Aplica regras fiscais (ST, ICMS, PIS/COFINS, CST etc) apenas para preview, não grava XML ainda

Adiciona item ao carrinho

Venda permanece status "ABERTO".

🟦 Passo 3 – Seleção do Método de Pagamento

PDV exibe apenas métodos permitidos pela filial (FilialMetodoPagamento).

Usuário seleciona método (ex.: PIX, Débito, Crédito).

Sistema verifica:

método ativo

se necessita TEF (utiliza_tef=True)

se terminal suporta TEF (terminal.permite_tef=True quando usa TEF)

Se o método não utiliza TEF, a venda segue diretamente para emissão fiscal.

🟦 Passo 4 – Resolução da Configuração TEF Efetiva

TEF síncrono precisa da configuração TEF correta.

O sistema busca a configuração:

config = TefConfig.get_effective_config(filial, terminal, provider=SITEF)


Regras:

Se existir config específica por terminal, usar essa.

Senão, usar config padrão da filial.

Se nenhuma existir:

PDV bloqueia o pagamento

Mensagem: “Configuração TEF não encontrada para este terminal.”

Elementos da configuração:

MerchantID

StoreID (opcional)

Host/Sitef IP / Porta

API key (via alias/cofre)

Ativo/inativo

🟦 Passo 5 – Início do Fluxo TEF (SINCRONO)
Este é o fluxo clássico, igual ao POS Controle:

PDV envia para o TEF:

- valor total da compra
- tipo de pagamento (crédito, débito, voucher, etc.)
- parcelas, se aplicável
- identificador do terminal no TEF (tef_terminal_id)
- merchant_id / store_id
- número da venda (NSU local)


A integração TEF retorna e exige:

esperar resposta (sincrono)

PDV fica travado aguardando confirmação ou erro

TEF retorna um dos estados:

a) Sucesso

autorizacao: código de autorização da adquirente

nsu_tef: número único TEF

bandeira

tipo (crédito/débito)

parcelas (se aplicável)

cartão mascarado (**** **** **** 1234)

comprovante_cliente

comprovante_estabelecimento

b) Erro (sem limite, erro de comunicação, cartão inválido etc.)

TEF retorna código de erro como:

sem limite

transação negada

cartão inválido

erro de comunicação

tempo excedido

Nesses casos:

Venda NÃO é finalizada
Não gera XML
PDV permanece na tela de pagamento
Usuário pode tentar outro pagamento ou cancelar a venda

🟦 Passo 6 – Persistência dos Dados TEF (somente sucesso)

Se TEF retornar sucesso:

PDV salva uma VendaPagamento com:

tipo pagamento

valor

nsu_tef

codigo_autorizacao

comprovante_cliente

comprovante_estabelecimento

bandeira

parcelas

Atualiza total pago.

Venda vai para status "PAGAMENTO_CONFIRMADO".

Agora sim, pode emitir documento fiscal.

🟦 Passo 7 – Envio para API Fiscal Externa

Usamos NDD, TecnoSpeed, ou API própria.

PDV monta o payload do XML (via provider externo).

Envia para API:

dados do emitente (filial)

produtos

impostos

pagamentos

valores

tipo documento (NFC-e / NFe)

identificação do terminal

identificação única da venda

API faz:

validação

montagem/fabricação do XML

assinatura com certificado da filial

envio para SEFAZ

aguarda retorno síncrono

API devolve para o PDV um JSON com:

sucesso

chave de acesso

XML autorizado

QRCODE (NFC-e)

DANFE (se houver)

número/serie

erro

código SEFAZ 225, 539, 806, 999 etc

descrição

🟦 Passo 8 – Tratamento do retorno da API
a) Se API retornar sucesso

PDV:

salva chave de acesso

salva XML autorizado

salva QRCODE

atualiza status = "FINALIZADA"

imprime DANFE NFC-e no mobile

b) Se API retornar erro

Exemplos:

erro 225 (cadastro inválido)

rejeição 601 (valor ICMS)

rejeição 999 (SEFAZ indisponível)

timeouts

Nestes casos:

Venda fica com status "ERRO_FISCAL"
Não finaliza
Pagamentos TEF devem estar habilitados para estorno manual ou automático (regra depende da adquirente).
Usuário pode:

tentar reenviar

corrigir cadastro

cancelar a venda

🟦 Passo 9 – Finalização

Somente após:

TEF concluído com sucesso

API fiscal autorizada retornando chave válida

A venda é considerada:

FINALIZADA

E os dados são gravados:

XML autorizado

QRCODE

comprovantes TEF

DANFE

PDV fecha a venda e retorna para nova operação.

🧩 10. Fluxo Completo Em Diagrama (alto nível)
[Usuário]
   ↓
[Seleciona produtos]
   ↓
[Carrinho ABERTO]
   ↓
[Seleciona método de pagamento]
   ↓
Se método utiliza TEF?
   ↓        ↓
Sim        Não
↓           ↓
[Buscar TefConfig]       [Pular TEF]
[Enviar transação TEF]
[TEF retorna sucesso?]
↓              ↓
Sim           Não
↓              ↓
[Salvar dados TEF]    [Permanece na tela de pagamento]
[status = PAGAMENTO_CONFIRMADO]
   ↓
[Enviar venda à API Fiscal]
   ↓
Aprovado?
↓           ↓
Sim         Erro
↓           ↓
[Salvar XML autorizado]  [status = ERRO_FISCAL]
[status = FINALIZADA]
   ↓
[Imprimir Nota]
   ↓
[Venda concluída]

🧩 11. Pontos Críticos e Boas Práticas de Arquitetura
✔ Evitar “finalizar venda” antes de TEF + Fiscal

Fluxo garantido.

✔ TEF síncrono bloqueia UI

Isso é o comportamento correto.

✔ Configurações TEF sempre por Filial ou Terminal

E validamos isso nos testes.

✔ Provedor Fiscal terceirizado

Delega XML, assinatura e SEFAZ para API externa.

✔ Tratamento de falhas com robustez

TEF negado → venda não finaliza

Fiscal rejeitado → venda fica no pipeline para ajuste

Sem internet → TEF falha → venda volta ao carrinho

✔ Registros completos de Logs

Incluso no nosso roadmap.
