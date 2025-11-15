# Catálogo de Erros de API — GetStart PDV

Este documento lista os **códigos de erro padronizados** retornados pela API, sua semântica e responsabilidade de correção.

A estrutura de erro é:

```json
{
  "error": {
    "code": "FISCAL_4005",
    "message": "Certificado A1 expirado para a filial.",
    "details": { ... }
  }
}
1. Convenções de códigos
Formato: GRUPO_NUMERO

AUTH_1xxx — Autenticação/autorização.

TENANT_1xxx — Problemas de tenant/multi-tenant.

FISCAL_4xxx — Erros fiscais (NFC-e).

SYNC_3xxx — Erros de sync/offline.

PAY_5xxx — Pagamentos (TEF, Pix, etc.).

COMMON_9xxx — Erros genéricos de infraestrutura/validação.

2. Erros de autenticação (AUTH_*)
Código	HTTP	Mensagem (resumo)	Responsável principal	Comentários
AUTH_1000	401	Token de autenticação ausente ou inválido.	Frontend/PDV	Usuário deve refazer login.
AUTH_1001	403	Usuário sem permissão para acessar o recurso.	Backend	Avaliar RBAC/permissões.
AUTH_1002	401	Refresh token inválido ou expirado.	Frontend/PDV	Refazer login.

3. Erros de tenant (TENANT_*)
Código	HTTP	Mensagem (resumo)	Responsável	Comentários
TENANT_1001	400	Cabeçalho X-Tenant-ID ausente.	Frontend/PDV	Sempre enviar tenant válido.
TENANT_1002	404	Tenant não encontrado para o X-Tenant-ID informado.	Infra/Backend	Verificar provisionamento de tenant.
TENANT_1003	403	Tenant inativo/bloqueado.	Comercial/Backend	Cliente sem acesso; validar contrato.

4. Erros fiscais (FISCAL_*)
Detalhados tecnicamente em docs/fiscal/erros_fiscais.md.

Principais códigos (resumo):

Código	HTTP	Mensagem (resumo)
FISCAL_4001	422	Filial sem certificado A1 configurado.
FISCAL_4005	422	Certificado A1 expirado para a filial.
FISCAL_4008	404	Terminal não encontrado ou não vinculado à filial.
FISCAL_4010	404	Reserva/Pré-emissão não encontrada para request_id.
FISCAL_4020	422	Cancelamento sem estorno financeiro prévio.

5. Erros de sync/offline (SYNC_*)
Código	HTTP	Mensagem (resumo)	Responsável
SYNC_3001	400	Payload de eventos offline inválido.	Frontend/PDV
SYNC_3002	409	Evento com local_tx_uuid duplicado já processado.	Backend (esperado)
SYNC_3003	422	Tipo de evento não suportado.	Backend

6. Erros de pagamento (PAY_*)
Código	HTTP	Mensagem (resumo)	Responsável
PAY_5001	422	Falha na autorização TEF.	Backend/Adquirente
PAY_5002	422	Transação TEF não encontrada para estorno.	Backend
PAY_5003	422	Falha na criação de cobrança Pix.	Backend/Gateway

Esses serão detalhados melhor quando o módulo de pagamento estiver implementado.

7. Erros comuns (COMMON_*)
| Código | HTTP | Mensagem (resumo) | Responsável |
|-------------|------|-----------------------------------------------------|
| COMMON_9001 | 400 | Dados de entrada inválidos (validação). |
| COMMON_9002 | 500 | Erro interno inesperado. |
| COMMON_9003 | 503 | Serviço temporariamente indisponível. |

8. Boas práticas de uso
Frontend/PDV deve sempre:

Ler o code.

Usar message para exibição amigável ao usuário.

Em caso de 4xx, validar se é problema de entrada/fluxo.

Em caso de 5xx, exibir mensagem genérica e logar para suporte.

Backend deve:

Garantir que todo erro previsto tenha um code mapeado.

Registrar detalhes técnicos em log (stacktrace, request_id), mas sem expor PII no details da resposta.
