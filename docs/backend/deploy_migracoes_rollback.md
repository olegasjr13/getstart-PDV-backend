# Deploy, Migrações e Rollback — GetStart PDV (Backend)

## 1. Objetivo

Este documento define o processo **oficial, seguro e padronizado** de deploy, migrações e rollback do backend do GetStart PDV, considerando:

- Arquitetura multi-tenant por schema  
- Operação fiscal sensível (NFC-e)  
- Ambientes dev, QA e produção  
- Containers imutáveis (Docker)  
- CI/CD seguro  
- Zero downtime  
- Conformidade semelhante ao POS Controle  

Este documento deve ser seguido **estritamente** por todas as equipes.

---

# 2. Estratégia Oficial de Deploy

Deploy deve seguir princípios:

- **Rolling Updates** → sem downtime  
- **Build imutável** → imagens versionadas  
- **Migrações aplicadas antes do tráfego**  
- **Healthchecks obrigatórios**  
- **Rollback rápido e limpo**  
- **Sem alteração manual de banco em produção**  

### Fluxo recomendado:

```
1. Build da imagem
2. Execução dos testes
3. Aplicação de migrações (public → tenants)
4. Deploy da nova imagem
5. Rotacionar tráfego após readiness OK
```

---

# 3. Deploy Multi-Tenant (Crítico)

O backend usa **1 banco com múltiplos schemas**, um por tenant.

### 3.1. Ordem obrigatória de migrações

```
(1) Migrar schema "public"
(2) Migrar schemas de tenants
```

### 3.2. Comando oficial

```
python manage.py migrate_schemas --executor=parallel
```

### 3.3. Quando não usar executor paralelo?

- Ambientes com grande número de schemas  
- Migrações pesadas  
- Migrações que alteram tabelas grandes  
- Produção com carga alta  

Nesses casos:

```
python manage.py migrate_schemas --executor=serial
```

---

# 4. Fluxo Oficial de Deploy (Passo a Passo)

## 4.1. CI — Build

- Criar imagem Docker do backend  
- Versão SemVer: `backend:vX.Y.Z`  
- Executar testes unitários  
- Executar linters  

## 4.2. Pré-Deploy

- Requisitar *freeze* temporário (opcional)  
- Verificar saúde do banco  
- Validar que não existem migrações perigosas  

## 4.3. Aplicação de Migrações

Ordem:

```
python manage.py migrate  # schema public
python manage.py migrate_schemas --executor=parallel
```

Se falhar → interromper deploy imediatamente.

## 4.4. Deploy

- Subir containers novos  
- Healthcheck `/health/liveness` deve passar  
- Orquestrador (Railway/Docker/K8s) troca instâncias gradualmente  

## 4.5. Pós-Deploy

- Validar readiness  
- Testar operação fiscal real (homologação)  
- Monitorar logs  

---

# 5. Migrações Seguras no PDV

Migrações devem seguir padrão “Expand → Migrate → Contract”.

### 5.1. Expand (compatível retroativamente)

- Criar novas colunas sem NOT NULL  
- Criar novas tabelas  
- Criar índices  
- Jamais remover colunas nesta fase  

### 5.2. Migrate (popular dados)

Usar `RunPython` com:

```python
@transaction.atomic
def forward(apps, schema_editor):
    ...

def reverse(apps, schema_editor):
    ...
```

### 5.3. Contract (remover antigo)

- Remover colunas substituídas  
- Remover índices antigos  
- APENAS após deploy garantido  

---

# 6. Rollback — Estratégia Oficial

Rollback é **permitido**, desde que siga regras.

### 6.1. Quando rollback é permitido

- Erro após deploy mas antes de tráfego completo  
- Migração reversível  
- Problema em container/app (não em banco)

### 6.2. Quando rollback é proibido

- Migrações que alteraram dados irreversíveis  
- Ajustes fiscais aplicados  
- Reversão parcial entre tenants  

### 6.3. Como executar rollback

```
1. Interromper tráfego para nova versão
2. Subir imagem anterior
3. Aplicar rollback de migrações (quando possível)
4. Validar serviço
```

### 6.4. Rollback de migrações

Se a migração tem reverse:

```
python manage.py migrate app X_previous_version
```

Se não tem reverse → **rollback parcial proibido**.

---

# 7. Procedimento de Emergência Fiscal

Se um deploy afetar emissão NFC-e:

### Ação imediata:

1. Redirecionar tráfego para imagem anterior  
2. Validar que clientes conseguem emitir mock/homolog  
3. Se numeração travou:
   - Forçar auditoria  
   - Verificar pré-emissões pendentes  
4. Se XMLs ficaram inconsistentes:
   - Reconciliação manual via auditoria  
   - Exportação dos eventos  
5. Confirmar retomada da operação fiscal  

---

# 8. Migrações que Impactam NFC-e (Atenção)

As tabelas abaixo **não podem sofrer alterações agressivas**:

- `NfceNumeroReserva`  
- `NfcePreEmissao`  
- `NfceDocumento`  
- `Filial`  
- `Terminal`  
- `Certificados`  

Proibições:

- Remover colunas sem transição  
- Alteração de tipos críticos  
- Adicionar NOT NULL sem default  
- Mudar regras de integridade sem coordenação  

---

# 9. CI/CD — Scripts Recomendados

### Build Docker

```bash
docker build -t backend:${VERSION} .
```

### Rodar Migrações

```bash
docker run backend:${VERSION} python manage.py migrate
docker run backend:${VERSION} python manage.py migrate_schemas --executor=parallel
```

### Validar Healthcheck

```
curl -f https://api.seuservico.com/health/readiness
```

---

# 10. Checklists Oficiais

## 10.1. Pré-Deploy

- [ ] Imagem gerada e testada  
- [ ] Migrações revisadas  
- [ ] Auditoria fiscal habilitada  
- [ ] Tenants ativos listados  
- [ ] Verificar compatibilidade fiscal  

## 10.2. Pós-Deploy

- [ ] Verificar liveness  
- [ ] Verificar readiness  
- [ ] Testar emissão mock  
- [ ] Testar emissão homolog  
- [ ] Verificar auditoria  
- [ ] Monitorar logs  

## 10.3. Rollback

- [ ] Desviar tráfego  
- [ ] Subir imagem anterior  
- [ ] Reverter migrações (quando permitido)  
- [ ] Validar emissão fiscal  
- [ ] Validar auditoria  
- [ ] Normalizar numeração  

---

# 11. Boas Práticas Gerais

- Sempre criar migrações reversíveis  
- Nunca alterar tabelas fiscais sem plano de testes  
- Usar feature flags quando possível  
- Testar com tenants reais  
- Garantir compatibilidade via expand/contract  
- Validar emissão fiscal após cada release  

---

# 12. Conclusão

Este documento define o padrão definitivo de:

- Deploy zero-downtime  
- Migrações seguras multi-tenant  
- Rollback responsável  
- Garantia de integridade fiscal  

Ele deve ser seguido rigorosamente para evitar perda de vendas, erros fiscais e inconsistências em produção.

