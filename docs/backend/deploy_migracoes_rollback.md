# Guia de Deploy, Migrações e Rollback — GetStart PDV Backend

## 1. Objetivo
Este documento define o processo oficial para:
- Gerar migrações
- Aplicar migrações em ambiente multi-tenant
- Executar deploy seguro
- Realizar rollback
- Evitar downtime e preservar dados fiscais

Baseado no projeto real: Django + django-tenants + PostgreSQL.

---

# 2. Migrações no Ambiente Multi-Tenant

## 2.1 Como funcionam as migrações no projeto
- `SHARED_APPS` migram apenas no schema `public`
- `TENANT_APPS` migram em TODOS os schemas de tenants
- O django-tenants gerencia isso via `TenantSyncRouter`

---

# 3. Como Criar Migrações

## 3.1 Localmente
```
python manage.py makemigrations
```

## 3.2 Revisar migrações
Checklist:
- Migration não destrutiva?
- Campos obrigatórios têm default?
- Sem dependências cíclicas?

---

# 4. Como Aplicar Migrações

## 4.1 Em desenvolvimento
```
python manage.py migrate_schemas --shared
```
ou
```
python manage.py migrate
```

`migrate_schemas` aplica:
- Shared → public
- Tenant → todos os schemas

---

# 5. Deploy Backend

## 5.1 Ordem correta do deploy em cluster real
1. Build da imagem Docker
2. Criar migrações
3. Executar migrações no ambiente:
   ```
   python manage.py migrate_schemas --executor=sync
   ```
4. Healthcheck `/health/`
5. Substituição das réplicas antigas

---

# 6. Estratégia de Deploy Sem Downtime

## 6.1 Zero-downtime com backwards compatibility
Sempre seguir:
1. Adicionar coluna nova
2. Deploy do backend usando coluna nova (opcional)
3. Remover coluna antiga

Nunca:
- Renomear tabelas no meio do deploy
- Remover colunas usadas no backend atual

---

# 7. Rollback

## 7.1 Quando é necessário
- Falha de migração
- Falha lógica em produção
- Bug crítico pós-deploy

## 7.2 Procedimento
1. Reverter imagem do backend
2. Reverter migrações:
```
python manage.py migrate <app> <migration_anterior>
```
3. Validar healthcheck

---

# 8. Logs e Auditoria Durante Deploys

Todos os deploys devem registrar:
- versão
- timestamp
- status (OK, WARNING, ERROR)
- migrações aplicadas

---

# 9. Boas Práticas Obrigatórias

- Nunca alterar dados fiscais manualmente
- Nunca rodar SQL destrutivo sem backup
- Sempre testar migrações em ambiente staging com 2+ tenants
- Sempre rodar testes fiscais após migrações

---

# 10. Conclusão
Este guia formaliza como realizar deploy e migrações com segurança no GetStart PDV, garantindo estabilidade multi-tenant, preservação de dados fiscais e capacidade de rollback rápida.
