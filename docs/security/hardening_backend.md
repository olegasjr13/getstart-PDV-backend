# Hardening Backend — GetStart PDV

## Objetivo
Este documento define práticas de segurança para o backend baseado em Django + django-tenants.

## 1. Configurações Sensíveis
- Nunca commitar `.venv/` ou credenciais.
- Usar variáveis de ambiente: DJANGO_SECRET_KEY, PGUSER, PGPASSWORD, SENTRY_DSN.

## 2. Segurança HTTP
- Habilitar Secure Cookies.
- HSTS, X-Frame-Options, X-Content-Type-Options.

## 3. Segurança Multi-Tenant
- Nunca acessar tenant sem middleware.
- Proibir queries cross-tenant.

## 4. Banco de Dados
- Senhas fortes.
- Privilégios mínimos para usuários de banco.
- Rotação de credenciais.

## 5. Logs
- Não logar dados sensíveis (CPF completo, senhas).

## 6. Dependências
- Rodar `pip-audit` semanalmente.
- Fixar versões em `requirements.txt`.

## 7. Produção
- Desabilitar DEBUG.
- Configurar ALLOWED_HOSTS.
