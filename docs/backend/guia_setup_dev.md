# Guia de Setup de Ambiente de Desenvolvimento — Backend GetStart PDV

## 1. Objetivo

Este guia explica, passo a passo, como um(a) desenvolvedor(a) backend deve:

- Configurar o ambiente local de desenvolvimento do **getstart-PDV-backend**.
- Subir a aplicação Django com PostgreSQL (multi-tenant via `django_tenants`).
- Rodar testes (Pytest) focados especialmente na parte fiscal (NFC-e).
- Criar dados mínimos para começar a desenvolver e testar.

> Este documento descreve **o fluxo atual do repositório backend**.
> Integrações com Docker/compose e outros ambientes ficam concentradas no repositório `getstart-PDV-infra`.

---

## 2. Visão geral do projeto

Principais diretórios na raiz:

```text
getstart-PDV-backend/
├── config/        # Configurações Django (settings, urls, wsgi, asgi)
├── commons/       # Componentes/infra comum
├── tenants/       # Multi-tenant (Tenant, Domain)
├── usuario/       # Usuários e autenticação
├── filial/        # Filiais
├── terminal/      # Terminais (PDVs)
├── fiscal/        # Módulo fiscal (NFC-e)
├── manage.py      # Entry point Django
├── pytest.ini     # Configuração Pytest
├── requirements.txt
└── .venv/         # (foi comitada; idealmente adicionar ao .gitignore futuramente)
O backend usa:

Django

Django REST Framework

django-tenants (PostgreSQL multi-tenant)

Pytest para testes

Sentry para monitoramento de erros

3. Pré-requisitos
3.1 Ferramentas

Para desenvolver localmente:

Python 3.x

PostgreSQL (rodando localmente)

Git

Opcional (futuro, via getstart-PDV-infra):

Docker + Docker Compose

3.2 Acesso ao repositório
git clone https://github.com/SEU_USUARIO/getstart-PDV-backend.git
cd getstart-PDV-backend

4. Configuração do banco PostgreSQL para dev

O arquivo config/settings.py usa as variáveis:

PGDATABASE (padrão: pdvdados)

PGUSER (padrão: postgres)

PGPASSWORD (padrão atual: "29032013" — somente para dev)

PGHOST (padrão: 127.0.0.1)

PGPORT (padrão: 5432)

4.1 Criar banco e usuário no PostgreSQL (exemplo)

No psql:

CREATE DATABASE pdvdados;
CREATE USER postgres WITH PASSWORD '29032013';
GRANT ALL PRIVILEGES ON DATABASE pdvdados TO postgres;


Em ambiente real/seguro, a senha não deve ser hardcoded nem fraca.
Para dev, isso é aceitável, mas será tratado em security/hardening_backend.md.

4.2 Configurar variáveis de ambiente (opcional)

Se quiser sobrescrever os padrões definidos em settings.py, você pode exportar:

export PGDATABASE=pdvdados
export PGUSER=postgres
export PGPASSWORD=29032013
export PGHOST=127.0.0.1
export PGPORT=5432

5. Variáveis de ambiente do Django

O config/settings.py já usa algumas envs importantes:

DJANGO_SECRET_KEY (padrão: "dev-only")

TENANT_PROVISIONING_TOKEN

ADMIN_PROVISIONING_TOKEN

SENTRY_DSN (padrão: vazio → Sentry desativado)

Para desenvolvimento local mínimo, você pode:

export DJANGO_SECRET_KEY="dev-secret-key-local"
export TENANT_PROVISIONING_TOKEN="dev-provisioning-token"
export ADMIN_PROVISIONING_TOKEN="dev-admin-token"
# SENTRY_DSN pode ficar vazio em dev, se não for necessário


Futuramente, será criado um env/.env.dev.example padronizado, mas no código atual essas variáveis já são opcionais ou têm default.

6. Criando e ativando o ambiente virtual

Recomendado usar um virtualenv fora da .venv/ comitada (idealmente ela será removida ou ignorada depois).

cd getstart-PDV-backend

python -m venv .venv_dev
source .venv_dev/bin/activate  # Linux/macOS
# .venv_dev\Scripts\activate   # Windows

pip install --upgrade pip
pip install -r requirements.txt

7. Aplicando migrações

Com o Postgres rodando e o virtualenv ativo:

python manage.py migrate


Isso vai:

Criar as tabelas no banco pdvdados.

Aplicar migrações do core, tenants, usuario, fiscal, etc.

8. Criando usuário admin e dados iniciais
8.1 Superusuário Django (admin)
python manage.py createsuperuser


Use esse usuário para acessar /admin/ e inspecionar modelos, tenants, etc.

8.2 Tenants, filiais, terminais e usuários demo

Hoje, o código já usa django_tenants e os testes fiscais mostram o padrão com:

schema_context

get_tenant_model

O plano é termos management commands como:

python manage.py create_demo_tenant
python manage.py create_demo_filial_terminal
python manage.py create_demo_users


Estado atual: esses comandos podem ainda não existir.
Neste momento, para criar dados:

Você pode usar o admin Django (/admin/) ou seguir os padrões usados nos testes em fiscal/tests/conftest.py e demais fixtures.

Futuramente, o arquivo docs/backend/scripts_seed_dados.md detalhará esses commands.

9. Rodando o servidor de desenvolvimento

Com envs configuradas, virtualenv ativo, banco e migrações ok:

python manage.py runserver 0.0.0.0:8000


A aplicação ficará disponível em:

http://localhost:8000/

URLs úteis:

http://localhost:8000/admin/ — Django Admin

Endpoints de API (definidos em config/urls.py / config/urls_public.py)

10. Rodando testes (Pytest)

O projeto já vem com pytest.ini:

[pytest]
DJANGO_SETTINGS_MODULE = config.settings
python_files = tests.py test_*.py *_tests.py


Para rodar todos os testes:

pytest


Ou, para focar nos testes fiscais (por exemplo):

pytest fiscal/tests/test_nfce_reserva.py
pytest fiscal/tests/test_nfce_idempotencia_mesmo_request_id.py


Os testes em fiscal/tests/ são referência de padrão para desenvolvimento de novos testes:

uso de pytest.mark.django_db

uso de schema_context para multi-tenant

uso de APIClient para simular chamadas REST

Um guia mais detalhado será descrito em:
docs/qa/guia_testes_backend.md.

11. Teste rápido do ambiente (smoke test dev backend)

Depois de subir o servidor:

Acesse /admin/ com seu superusuário.

Confirme que consegue:

Ver models de tenants, filial, terminal, fiscal.

(Opcional) Rode um teste fiscal simples:

pytest fiscal/tests/test_nfce_reserva.py


Se esse teste passar, significa que:

Banco + tenants estão ok.

Configuração básica de NFCE reserva está funcional.

12. Problemas comuns (troubleshooting)
12.1 Erro de conexão com banco

Verifique se o serviço PostgreSQL está rodando.

Confirme:

PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD.

Caso esteja usando defaults, o banco deve ser acessível em:

host: 127.0.0.1

port: 5432

db: pdvdados

user: postgres

12.2 Erros em testes relacionados a tenants

Alguns testes usam schema_context e criação explícita de tenant.

Se algo falhar:

Verifique se as migrations do app tenants foram aplicadas.

Veja fiscal/tests/conftest.py e demais fixtures como referência.

13. Próximos passos para o dev backend

Depois de conseguir:

Subir o projeto

Rodar migrações

Rodar testes básicos

Recomendamos:

Ler docs/arquitetura/overview.md e docs/arquitetura/dominios.md.

Ler docs/api/dicionario_endpoints.md para entender os endpoints.

Ler docs/fiscal/regras_fiscais.md se for trabalhar na parte NFC-e.

Ler docs/backend/padroes_backend.md (quando criado) para seguir o padrão de:

services

views

serializers

especialmente no app fiscal.
