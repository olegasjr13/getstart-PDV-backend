# XML de NFC-e e Client MOCK — GetStart PDV

## 1. Objetivo

Este documento define:

- Como o backend do GetStart PDV **monta e utiliza** o XML de NFC-e.
- Como funciona o **client MOCK de SEFAZ** para desenvolvimento/QA.
- Qual é o **contrato** entre o `NfceEmissaoService` e os clients SEFAZ (mock e reais).
- Como o sistema escolhe entre:
  - Emissão via MOCK
  - SEFAZ Homologação
  - SEFAZ Produção

O foco é permitir:

- Desenvolvimento e testes sem necessidade de certificado A1 real.
- QA com cenários controlados (autorização, rejeição, erro).
- Evolução simples para clients reais por UF (SP, MG, RJ, ES).

> Este documento complementa:
> - `regras_fiscais.md` (regras e fluxos fiscais)
> - `sefaz_clients_arquitetura.md` (arquitetura dos clients por UF)
> - `auditoria_nfce.md` (auditoria de emissão)
> - `padroes_logs_backend.md` / `logbook_eventos.md` (logs fiscais)

---

## 2. Visão Geral

### 2.1. Camadas Envolvidas

No fluxo de emissão, temos:

1. **`NfcePreEmissao`**
   - Contém o **payload da venda** (itens, totais, pagamentos etc.).
   - É persistido antes da emissão.

2. **Montagem de XML** (responsabilidade da camada fiscal)
   - Converte o payload em XML no layout exigido pela NFC-e.

3. **Client SEFAZ**
   - Implementa o contrato `SefazClientProtocol`.
   - Pode ser:
     - `SefazClientMock` (desenvolvimento/QA)
     - `SefazClientSP`, `SefazClientMG`, `SefazClientRJ`, `SefazClientES` (reais, por UF).

4. **`NfceEmissaoService`**
   - Orquestra a emissão:
     - Busca a pré-emissão.
     - Resolve filial/terminal/ambiente.
     - Chama o client SEFAZ adequado.
     - Trata resposta e atualiza auditoria/logs.

---

## 3. Contrato do Client SEFAZ (`SefazClientProtocol`)

Todos os clients SEFAZ (mock e reais) devem implementar a seguinte interface:

```python
class SefazClientProtocol(Protocol):
    def emitir_nfce(self, *, pre_emissao: NfcePreEmissao) -> dict:
        ...
3.1. Entrada

pre_emissao: instância de NfcePreEmissao contendo:

filial_id

terminal_id

numero

serie

request_id

payload (dados da venda, já validados).

3.2. Saída (dicionário padronizado)

O retorno deve ser um dict com, no mínimo, os campos:

{
    "status": "AUTORIZADA" | "REJEITADA" | "ERRO",
    "codigo": "<codigo_retorno_sefaz_ou_mock>",
    "mensagem": "<mensagem_humana>",
    "chave": "<chave_nfe_44_digitos_ou_mock>",
    "protocolo": "<numero_protocolo_ou_mock>",
    "xml_enviado": "<xml_assinado_em_string>",
    "xml_resposta": "<xml_resposta_em_string_ou_vazio>",
    "raw": { ... }  # dict com o raw original da SEFAZ/motor interno
}


Regra importante:
O NfceEmissaoService não deve precisar saber se o client é mock ou real. Ele só reage ao status/codigo/mensagem do contrato acima.

4. Client MOCK de NFC-e
4.1. Objetivo

O SefazClientMock é usado em:

Ambientes de desenvolvimento (dev).

Ambientes de QA (testes automatizados/manual sem SEFAZ real).

Seeds (seed_dados) e testes de ponta a ponta controlados.

Ele permite:

Emitir NFC-e sem certificado A1.

Simular cenários de:

Autorização.

Rejeição.

Erro técnico.

4.2. Estratégia de Geração de XML

O mock não precisa seguir 100% do layout oficial na primeira fase, mas deve:

Gerar um XML bem formado, com:

Cabeçalho básico (cUF, cNF, natOp, mod, série, número, etc.).

Dados do emitente (CNPJ/Filial).

Dados do destinatário (quando existir).

Itens da venda (produtos, CFOP, NCM, valores).

Totais (ICMS, ICMS-ST, PIS/COFINS, etc. — mesmo que simplificados).

Dados de pagamento (cartão, dinheiro, etc.).

O objetivo é:

Permitir testes de montagem/parse do XML dentro do backend.

Permitir evolução suave para uso do mesmo “builder” de XML em clients reais.

4.3. Geração de CHAVE e PROTOCOLO (mock)

Para o mock, a chave de acesso (chave) e protocolo podem ser gerados internamente:

chave:

String com 44 dígitos, montagem “fake” porém coerente:

UF (cUF)

Ano/mês

CNPJ

Modelo

Série

Número

Tipo de emissão

Código numérico

DV

Não precisa ter validação oficial em ambientes dev/qa.

protocolo:

String numérica simulando o formato da SEFAZ.

5. Cenários de Mock

O SefazClientMock.emitir_nfce deve permitir simular diferentes cenários com base em:

Flags no payload.

Valores específicos (ex.: total da venda).

Dados artificiais (ex.: cliente com CPF “forçado” para rejeição).

5.1. Emissão bem-sucedida (AUTORIZADA)

Regra sugerida:

Cenário padrão → se não houver nenhuma “flag de erro” no payload, o mock retorna:

{
    "status": "AUTORIZADA",
    "codigo": "100",
    "mensagem": "Autorizado o uso da NF-e (MOCK)",
    "chave": "<chave_mock>",
    "protocolo": "<protocolo_mock>",
    "xml_enviado": "<xml_assinado_mock>",
    "xml_resposta": "<xml_resposta_mock>",
    "raw": { "mock": True, "cenario": "AUTORIZADA" }
}


Logs obrigatórios: nfce_emissao_mock_sucesso
Auditoria: recomendada em QA, opcional em dev.

5.2. Rejeição (REJEITADA)

O mock deve permitir simular rejeições comuns, por exemplo:

CFOP inválido para operação.

NCM inexistente.

Total da NF e soma dos itens divergente.

Uso de campo customizado no payload ("mock_rejeicao": "XXX").

Exemplo de regra simples:

Se o payload contiver:

"mock_rejeicao": {
    "codigo": "999",
    "mensagem": "Rejeição mock configurada"
}


então o client retorna:

{
    "status": "REJEITADA",
    "codigo": "999",
    "mensagem": "Rejeição mock configurada",
    "chave": None,
    "protocolo": None,
    "xml_enviado": "<xml_assinado_mock>",
    "xml_resposta": "<xml_resposta_mock_rejeicao>",
    "raw": { "mock": True, "cenario": "REJEITADA" }
}


Logs obrigatórios: nfce_emissao_mock_erro
Auditoria: opcional (em QA, pode ser usado para trilha completa de rejeições).

5.3. Erro técnico (ERRO)

Também é útil simular erros técnicos:

Timeout.

Falha de comunicação.

Exceção interna.

Pode ser feito com uma flag no payload, ex.:

"mock_erro": {
    "tipo": "TIMEOUT",
    "mensagem": "Timeout simulado na comunicação com SEFAZ (mock)"
}


O client pode:

Lançar uma exceção específica (capturada pelo NfceEmissaoService), ou

Retornar status="ERRO" com detalhamento em codigo/mensagem.

Exemplo de resposta:

{
    "status": "ERRO",
    "codigo": "MOCK_TIMEOUT",
    "mensagem": "Timeout simulado na comunicação com SEFAZ (mock)",
    "chave": None,
    "protocolo": None,
    "xml_enviado": "<xml_assinado_mock>",
    "xml_resposta": "",
    "raw": { "mock": True, "cenario": "ERRO", "tipo": "TIMEOUT" }
}


Logs obrigatórios: nfce_emissao_mock_erro
Sentry: pode ser usado quando for interessante ver stack trace mesmo em ambiente de QA.

6. Seleção entre MOCK, Homologação e Produção

A escolha de qual client usar não deve ficar no código do PDV/app, e sim na configuração de backend (multi-tenant + filial).

6.1. Estratégia recomendada

Campos na Filial (exemplo):

uf — UF da filial (SP, MG, RJ, ES).

nfce_ambiente — "mock" | "homolog" | "producao".

6.2. Factory de clients

Função (descrita em detalhes em sefaz_clients_arquitetura.md):

def get_sefaz_client(*, uf: str, ambiente: str, filial: Filial) -> SefazClientProtocol:
    if ambiente == "mock":
        return SefazClientMock()
    if uf == "SP":
        return SefazClientSP(...)
    if uf == "MG":
        return SefazClientMG(...)
    ...

6.3. Uso no NfceEmissaoService

O service faz:

Busca NfcePreEmissao por request_id.

Busca Filial e valida nfce_ambiente.

Chama get_sefaz_client(uf=filial.uf, ambiente=filial.nfce_ambiente, filial=filial).

Chama client.emitir_nfce(pre_emissao=pre_emissao).

Dessa forma:

Em dev/qa → nfce_ambiente = "mock" → usa SefazClientMock.

Em homologação → nfce_ambiente = "homolog" → usa client real apontando para SEFAZ homolog.

Em produção → nfce_ambiente = "producao" → usa client real apontando para SEFAZ produção.

7. Logs e Auditoria ligados ao MOCK

Mesmo com mock, algumas coisas devem ser seguidas:

Eventos de log:

nfce_emissao_mock_sucesso

nfce_emissao_mock_erro

Campos de contexto obrigatórios:

tenant_id, filial_id, terminal_id, user_id, request_id, numero, serie.

Auditoria:

Dev: opcional.

QA: recomendado (NfceAuditoria marcando ambiente="mock").

A ideia é que a infra/observabilidade consiga ver claramente:

Quando a emissão é mock.

Qual cenário de mock foi disparado (autorizado, rejeitado, erro).

8. Considerações de Segurança e Compliance

Mesmo no mock:

Não logar dados sensíveis (cartão, senhas, etc.).

Não expor chaves reais ou certificados em logs.

O mock não deve ser utilizado em ambiente de produção.

Em produção:

O uso de client mock deve estar bloqueado por configuração.

Toda emissão deve passar por:

Certificado A1 válido.

Client real por UF.

Auditoria em banco.

9. Evolução

Conforme o projeto avançar:

O mock poderá:

Validar schemas XML contra XSD local.

Simular perfis mais complexos de rejeição.

Ser usado em testes automatizados de integração.

Clients reais por UF (SP, MG, RJ, ES) serão implementados usando a mesma estrutura de montagem de XML.

Sempre que o contrato do SefazClientProtocol for alterado, este documento deve ser atualizado.
