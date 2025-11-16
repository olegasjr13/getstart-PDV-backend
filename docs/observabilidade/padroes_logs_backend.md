# Padrões de Logs do Backend — GetStart PDV

## 1. Objetivo

Este documento define os **padrões obrigatórios de logging** para o backend multi-tenant do GetStart PDV, com foco em:

- Rastreabilidade ponta-a-ponta (request → serviço → SEFAZ).
- Auditoria fiscal (NFC-e).
- Diagnóstico rápido em produção (observabilidade).
- Integração com stacks externas (Sentry, ELK, Loki, etc.).

Os padrões aqui descritos **são mandatórios** para todo novo código de backend.

---

## 2. Princípios Gerais

1. **Logs estruturados (JSON)**
   Todos os logs devem ser emitidos em formato JSON, compatível com o formatter configurado no `settings.py` (via `python-json-logger`).

2. **Contexto completo**
   Sempre que possível, os logs devem conter:
   - `tenant_id` (CNPJ raiz do tenant).
   - `schema_name` (schema do tenant).
   - `filial_id`.
   - `terminal_id`.
   - `user_id`.
   - `request_id`.

3. **Nada sensível em log**
   É **proibido** logar:
   - Senhas, PINs, tokens de autenticação.
   - Dados de cartão (PAN, CVV).
   - CPF/CNPJ completos (usar mascaramento quando necessário).
   - XML fiscal completo com dados sensíveis (quando inevitável, considerar mascarar partes).

4. **Padronização por módulo**
   Cada evento importante de negócio deve ter:
   - Um **nome de evento** (`event`) padronizado.
   - Campos mínimos de contexto (vide seção 5).
   - Alinhamento com o catálogo em `logbook_eventos.md`.

---

## 3. Formato Base do Log

O formato final é determinado pelo formatter JSON da configuração de logging, mas todos os logs **de aplicação** devem seguir a seguinte estrutura conceitual:

```json
{
  "timestamp": "2025-01-01T12:00:00.123Z",
  "level": "INFO",
  "logger": "pdv.fiscal",
  "service": "backend",
  "environment": "prod",

  "event": "nfce_pre_emissao",
  "message": "Pré-emissão de NFC-e registrada",

  "tenant_id": "12345678000199",
  "schema_name": "tenant_12345678000199",
  "filial_id": "a7efae65-640e-49dd-bef2-9ced32fa8b84",
  "terminal_id": "5f2b39ed-90d0-4800-be75-f1aced155c21",
  "user_id": 1,
  "request_id": "e2557ca7-031a-4b94-afc0-434a2c6d929c",

  "http_method": "POST",
  "path": "/api/fiscal/nfce/pre-emissao/",
  "status_code": 201,

  "extra": {
    "numero": 123,
    "serie": 1,
    "uf": "SP"
  }
}
OBS: a chave exata (extra / campos soltos) pode variar conforme a config, mas os campos de contexto listados acima devem estar presentes.

4. Geração e Propagação de request_id
4.1. Middleware de request

O middleware de request do app commons é o responsável por:

Ler o header X-Request-ID se presente.

Gerar um novo UUID se o header não existir.

Anexar o request_id ao objeto request.

Logar automaticamente uma entrada de acesso HTTP contendo:

request_id, path, method, status_code, latency_ms.

Esse log automático é o mínimo obrigatório para rastreamento de requisições HTTP.

4.2. Uso em código de aplicação

Dentro de views, services e tasks, adotar o padrão:

logger = logging.getLogger("pdv.fiscal")

logger.info(
    "nfce_pre_emissao",
    extra={
        "event": "nfce_pre_emissao",
        "tenant_id": tenant.cnpj_raiz,
        "schema_name": connection.schema_name,
        "filial_id": str(filial.id),
        "terminal_id": str(terminal.id),
        "user_id": request.user.id,
        "request_id": request.request_id,
        "numero": pre_emissao.numero,
        "serie": pre_emissao.serie,
    },
)


Regra: sempre que logar algo de negócio, incluir event e o máximo de contexto disponível.

5. Campos Obrigatórios

Em qualquer log de negócio (INFO/WARNING/ERROR) emitido pelo código de aplicação, os seguintes campos são obrigatórios, quando aplicáveis:

event — nome do evento de negócio.

tenant_id — CNPJ raiz (pode vir de Tenant ou claims do token).

schema_name — schema atual (connection.schema_name).

filial_id — UUID da filial (se a operação for atrelada à filial).

terminal_id — UUID do terminal (quando aplicável).

user_id — ID do usuário autenticado (se houver).

request_id — UUID de correlação (sempre que houver request HTTP).

http_method — método HTTP (para logs em views).

path — caminho da requisição (para logs em views).

status_code — status HTTP (quando fizer sentido).

Campos de negócio relevantes (ex: numero, serie, chave).

Quando algum desses campos não se aplica (ex.: task agendada sem usuário nem request), registrar explicitamente com null ou omitir, mas manter event e contexto mínimo do processo.

6. Eventos Obrigatórios por Módulo

Os nomes abaixo devem ser usados como padrão base e alinhados com logbook_eventos.md.

6.1. Fiscal (NFC-e)

nfce_reserva_numero

Quando um número de NFC-e é reservado para um terminal/série.

nfce_pre_emissao

Quando a pré-emissão é registrada no banco (NfcePreEmissao).

nfce_emissao_mock_sucesso

Emissão bem-sucedida usando client MOCK (dev/qa).

nfce_emissao_mock_erro

Erro ao emitir usando MOCK.

nfce_emissao_sefaz_sucesso (futuro)

Emissão autorizada pela SEFAZ.

nfce_emissao_sefaz_rejeitada (futuro)

Rejeição da SEFAZ (código/motivo no extra).

nfce_cancelamento_sucesso (futuro)

nfce_cancelamento_falha (futuro)

nfce_inutilizacao_sucesso (futuro)

nfce_inutilizacao_falha (futuro)

6.2. Autenticação

auth_login_sucesso

auth_login_falha

auth_refresh_sucesso

auth_refresh_falha

Contexto obrigatório:

tenant_id, filial_id, terminal_id (quando disponíveis).

user_id para sucesso.

Motivos de erro no extra (sem expor senha).

6.3. Multi-tenant

tenant_context_loaded

Sempre que o contexto de tenant for resolvido a partir de X-Tenant-ID.

tenant_schema_mismatch_warning

Situações suspeitas de schema errado para um tenant.

tenant_inactive_access_blocked

Quando um tenant inativo tenta acessar o sistema.

6.4. Infra / Healthchecks

health_liveness_check

health_readiness_check

Esses logs podem ser em nível DEBUG em produção para evitar ruído excessivo, dependendo da estratégia da infra.

7. Níveis de Log

DEBUG

Informações detalhadas úteis apenas em desenvolvimento ou troubleshooting específico.

Não habilitar em produção por padrão.

INFO

Eventos normais de negócio:

Emissão bem-sucedida, login, reserva de número, etc.

WARNING

Situações anômalas, mas não fatais:

Tentativa de uso de tenant inativo.

Timeout de integração com SEFAZ com retry bem-sucedido.

ERROR

Falhas tratadas, mas que impactam o usuário ou o fluxo:

Rejeição SEFAZ.

Falha ao gravar pré-emissão.

Erro na camada de serviço que retornou 4xx/5xx.

CRITICAL

Situações fatais:

Erro de configuração grave.

Perda de conexão com banco em produção por longos períodos.

8. Integração com Sentry

Eventos de nível ERROR e CRITICAL devem ser capturados pelo Sentry.

Sempre que houver exceção não tratada, usar:

logger = logging.getLogger(__name__)

try:
    ...
except Exception:
    logger.exception(
        "unexpected_error_in_nfce_emissao",
        extra={
            "event": "nfce_emissao_unexpected_error",
            "tenant_id": ...,
            "filial_id": ...,
            "terminal_id": ...,
            "request_id": ...,
        },
    )
    raise


O Sentry receberá:

Stack trace completo.

Campos extras (tenant_id, filial_id, etc.) como contexto para triagem.

9. Relação com Auditoria em Banco

Além dos logs JSON, eventos críticos de NFC-e (emissão, cancelamento, inutilização, etc.) devem ser registrados também em tabelas de auditoria específicas (ver auditoria_nfce.md).

Regra:

Logs JSON → focados em observabilidade / troubleshooting.

Tabelas de auditoria → focadas em compliance e trilha fiscal.

Ambos devem compartilhar o mesmo request_id e chave de contexto para permitir reconciliação.

10. Conclusão

Seguir estes padrões garante que:

Cada requisição possa ser rastreada de ponta a ponta (request_id).

Cada operação fiscal relevante possa ser auditada (logs + DB).

A multi-tenancy seja respeitada em todos os logs (tenant/schema corretos).

A observabilidade seja consistente, independente da stack de logs adotada.

Qualquer novo módulo ou serviço deve estender este padrão, nunca criar formatos paralelos.
