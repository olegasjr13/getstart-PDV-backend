# Healthchecks — GetStart PDV (Versão Enterprise)
Versão: 1.0  
Responsável: Arquitetura Backend  

---

# 1. Objetivo
Este documento oficial define todos os **healthchecks** usados no backend GetStart PDV, incluindo:
- readiness (pronto para receber tráfego)
- liveness (processo ativo)
- dependências críticas (DB, tenants)
- verificações fiscais
- verificações futuras (SEFAZ, Redis, filas)
- responses padronizadas

Ele atende aos requisitos para:
- NGINX
- Railway / AWS
- Kubernetes (futuro)
- Monitoramento e SRE

---

# 2. Endpoints Oficiais de Healthcheck

O backend expõe três níveis:

```
/health
/health/live
/health/ready
```

---

# 3. Liveness — `/health/live`

## Objetivo
Verificar se o processo Django está **vivo e executando**.

## Regras
- NÃO deve verificar banco de dados.
- Usado por orquestradores para saber se o processo morreu.

## Resposta
```json
{
  "status": "live"
}
```

## Código HTTP
`200 OK`

---

# 4. Readiness — `/health/ready`

## Objetivo
Verificar se o backend está **pronto para receber requisições**.

## Validações obrigatórias:
1. Django carregou corretamente  
2. Banco `public` responde  
3. Migrations aplicadas no nível shared  
4. Django-tenants está operacional  
5. Leitura mínima do ORM funciona  

## Resposta
```json
{
  "status": "ready",
  "database": "ok",
  "migrations": "ok",
  "tenants": "ok"
}
```

## Falhas possíveis
- Banco offline  
- Erro ao carregar tenants  
- Migrações faltando  

---

# 5. Health Geral — `/health`

## Objetivo
Consolidar liveness + readiness.

## Resposta exemplo:
```json
{
  "status": "ok",
  "live": true,
  "ready": true,
  "timestamp": "2025-01-10T12:00:00Z"
}
```

---

# 6. Health Multi-Tenant (interno)

Este check é executado **internamente** (não exposto publicamente):

## Verificações obrigatórias:
- Carregar TenantModel
- Verificar existência de pelo menos 1 tenant
- Validar schema_name
- Validar Domain

Exemplo interno:
```json
{
  "tenants_count": 4,
  "schemas_ok": true
}
```

---

# 7. Health Fiscal (Mock)

## Objetivo
Garantir que o ambiente fiscal esteja pronto para gerar XML MOCK.

### Verificações:
- XMLBuilder carregado
- Serviço de keygen funcionando
- Pré-emissão acessível
- Geração de chave no mock sem exceção

### Resposta exemplo:
```json
{
  "fiscal": {
    "mock_builder": "ok",
    "qrcode_generator": "ok"
  }
}
```

---

# 8. Health SEFAZ (futuro)

Quando o sistema emitir NFC-e real:

### Checks obrigatórios:
- status do webservice autorizador  
- certificado A1 válido  
- comunicação com SVRS  

```json
{
  "sefaz": {
    "status": "ok",
    "certificado": "válido",
    "ambiente": "producao"
  }
}
```

---

# 9. Health Redis / Fila (futuro)

Para fila de processamento offline.

---

# 10. Códigos HTTP e boas práticas

| Check | HTTP | Deve falhar deploy? |
|-------|-------|----------------------|
| live | 200 | não |
| ready | 200/503 | sim |
| health | 200/503 | sim |

---

# 11. Segurança

- Nenhum check deve expor stacktrace.
- Nenhum check deve retornar dados sensíveis.
- Nenhum check deve retornar SQL.
- Em caso de falha: mensagem curta e objetiva.

Exemplo seguro:
```json
{
  "status": "error",
  "reason": "database_unavailable"
}
```

---

# 12. Conclusão
Este guia define todos os healthchecks oficiais do GetStart PDV.  
Eles são compatíveis com pipelines de deploy, NGINX, Railway/AWS e padrões enterprise.
