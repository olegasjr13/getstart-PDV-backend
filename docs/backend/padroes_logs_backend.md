# Padrões de Logs Backend — GetStart PDV

## 1. Objetivo
Definir padrões obrigatórios de logging para o backend multi-tenant e fiscal do GetStart PDV, garantindo rastreabilidade, auditoria e diagnósticos eficientes.

## 2. Princípios
- Logs devem ser **estruturados** (JSON).
- Todos os logs devem conter **tenant**, **filial**, **terminal** e **request_id** quando aplicável.
- Nada sensível deve ser logado (CPF completo, tokens, senhas).

## 3. Formato Base
```
{
  "timestamp": "...",
  "level": "INFO",
  "service": "fiscal",
  "event": "fiscal_reserva_criada",
  "tenant": "12345678000199",
  "filial": "FILIAL-1",
  "terminal": "T1",
  "request_id": "uuid",
  "payload": {...}
}
```

## 4. Campos Obrigatórios
- timestamp  
- level  
- event  
- tenant  
- schema_name  
- http_method  
- path  
- user_id (quando autenticado)  

## 5. Eventos Obrigatórios por Módulo

### 5.1 Fiscal
- fiscal_reserva_criada  
- fiscal_pre_emissao_registrada  
- fiscal_emitida_mock  
- fiscal_emitida_sefaz (futuro)
- fiscal_cancelada (futuro)

### 5.2 Autenticação
- auth_login_success  
- auth_login_failed  
- auth_refresh  

### 5.3 Multi-Tenant
- tenant_context_loaded  
- tenant_schema_mismatch_warning  

---

## 6. Níveis de Log
- INFO = Eventos normais de negócio  
- WARNING = Eventos suspeitos  
- ERROR = Falhas tratadas  
- CRITICAL = Falhas fatais  

---

## 7. Localização dos Logs
Todos devem ir para stdout (Docker friendly).

---

## 8. Integração com Sentry
- Capturar ERROR e CRITICAL
- Breadcrumbs com tenant, filial, terminal

---

## 9. Conclusão
Estes padrões garantem rastreabilidade completa, incluindo trilha fiscal e correlação multi-tenant.
