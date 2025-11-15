## `fiscal/erros_fiscais.md`

```markdown
# Catálogo de Erros Fiscais (`FISCAL_*`)

Este documento detalha todos os erros fiscais do domínio NFC-e, seus cenários e responsabilidades.

A resposta segue o padrão:

```json
{
  "error": {
    "code": "FISCAL_4005",
    "message": "Certificado A1 expirado para a filial.",
    "details": { ... }
  }
}
1. FISCAL_4001 — Filial sem certificado A1
HTTP: 422 Unprocessable Entity

Mensagem: Filial sem certificado A1 configurado.

Cenário:

Ao tentar reservar, pré-emitir ou emitir NFC-e, a Filial não possui certificado A1 cadastrado.

Causas prováveis:

Implantação incompleta.

Erro de cadastro ou migração.

Ação:

Cadastrar certificado A1 na Filial e repetir a operação.

Responsável principal: Backoffice / Implantação fiscal.

Logs recomendados:

filial_id, tenant_id, user_id, endpoint.

2. FISCAL_4005 — Certificado A1 expirado
HTTP: 422 Unprocessable Entity

Mensagem: Certificado A1 expirado para a filial.

Cenário:

A data atual é posterior à data de expiração do certificado.

Causas:

A1 não renovado.

Data/hora do servidor incorreta (verificar).

Ação:

Renovar certificado A1.

Atualizar A1 no cadastro da Filial.

Detalhes no details:

a1_expires_at.

Responsável: Cliente + Equipe de Implantação.

3. FISCAL_4008 — Terminal inválido ou não vinculado à Filial
HTTP: 404 Not Found

Mensagem: Terminal não encontrado ou não vinculado à filial.

Cenário:

terminal_id enviado no body não existe no schema do tenant.

Ou existe, mas vinculado a outra filial.

Ação:

Validar se o PDV está usando o terminal correto.

Conferir cadastro do terminal no backend.

Responsável: Backend (cadastro) + PDV (uso correto).

4. FISCAL_4010 — Pré-emissão/Reserva não encontrada
HTTP: 404 Not Found

Mensagem: Pré-emissão ou reserva não encontrada para o request_id informado.

Cenário:

Ao chamar /fiscal/nfce/pre-emissao ou /fiscal/nfce/emissao:

O backend não encontra NfceNumeroReserva ou NfcePreEmissao para o request_id.

Causas:

PDV pulou a etapa de reserva.

request_id diferente (erro de fluxo ou bug).

Ação:

Retentar fluxo correto: reservar → pré-emissão → emissão.

Corrigir PDV se estiver gerando request_id diferente a cada etapa.

Responsável: PDV + Backend (validação de fluxo).

5. FISCAL_4020 — Cancelamento sem estorno financeiro
HTTP: 422 Unprocessable Entity

Mensagem: Estorno financeiro obrigatório antes de cancelar a NFC-e.

Cenário:

Ao tentar cancelar uma NFC-e:

Não há registro de estorno financeiro para aquela venda em CaixaMovimento / Pagamentos.

Regra de negócio:

Nenhuma NFC-e pode ser cancelada sem que o dinheiro ou transação financeira tenham sido corretamente estornados.

Ação:

Efetuar estorno no módulo de caixa/pagamentos.

Retentar cancelamento.

Responsável: Operação de loja + PDV.

6. FISCAL_4030 — Inconsistência de totais da NFC-e (sugerido)
HTTP: 422 Unprocessable Entity

Mensagem: Totais da NFC-e inconsistentes com itens e pagamentos.

Cenário:

Soma dos itens ≠ valor_itens.

Ou valor_nfce ≠ valor_itens - descontos + acréscimos.

Ou soma dos pagamentos ≠ valor_nfce + troco.

Ação:

PDV deve recalcular totais localmente antes de enviar.

Responsável: PDV.

7. FISCAL_4040 — Operação fiscal não permitida no ambiente atual
HTTP: 403 Forbidden

Mensagem: Operação fiscal não permitida no ambiente atual.

Cenário:

Tentativa de executar operação de teste em Filial configurada como producao (se política proibir).

Ou operação de produção em Filial marcada como homologacao, se houver restrição.

Ação:

Verificar ambiente da Filial.

Ajustar uso de ambiente conforme política fiscal.

Responsável: Backend + Implantação.

8. Boas práticas
Cada erro fiscal deve:

Ter log com contexto completo (tenant_id, filial_id, terminal_id, request_id, user_id, endpoint).

Evitar expor detalhes sensíveis (conteúdo de A1, chaves internas) em details.

O PDV deve:

Tratar erros 4xx como ajuste de fluxo/dados.

Tratar 5xx como falha temporária/infraestrutura.
