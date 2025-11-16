
---

# 2. `docs/backend/scripts_seed_dados.md`

> O arquivo atual descreve comandos `create_demo_*`, mas o que combinamos foi um **único comando `seed_dados` com perfis** (`dev`, `qa`, `demo`) e suporte a CFOP/NCM e múltiplas UFs (SP, MG, RJ, ES). :contentReference[oaicite:1]{index=1}

Abaixo está a versão ajustada para essa estratégia. Substitua o conteúdo atual de `scripts_seed_dados.md` por este:

---

```md
# Scripts de Seed de Dados — GetStart PDV Backend

## 1. Objetivo

Padronizar os **scripts oficiais de seed de dados** do backend do GetStart PDV, garantindo que:

- Todo desenvolvedor consiga subir um ambiente funcional em poucos comandos.
- QA tenha uma massa de dados previsível e idempotente.
- Demonstrações (demo) usem dados consistentes.
- Seeds respeitem o modelo **multi-tenant** e as necessidades fiscais (CFOP/NCM para SP, MG, RJ, ES).

---

## 2. Conceito de Perfis de Seed

Todo seed será executado por meio de **um único comando**:

```bash
python manage.py seed_dados --profile=<perfil>
Perfis suportados:

dev → ambiente de desenvolvimento.

qa → ambiente de testes (automatizados e manuais).

demo → ambiente de demonstração comercial.

Cada perfil controla quantidade e tipo de dados criados, conforme descrito abaixo.

3. Perfil dev
3.1. Objetivo

Fornecer um ambiente de desenvolvimento rico em dados, com flexibilidade para testar cenários diversos (multi-tenant, múltiplas filiais, múltiplos terminais).

3.2. Dados Criados

Tenants de desenvolvimento

Criar pelo menos 1 tenant principal com CNPJ raiz fictício:

12345678000199 — Tenant Dev Principal

Opcionalmente, podem ser criados mais tenants para testar isolamento multi-tenant.

Filiais e UFs

Para o tenant principal, criar filiais cobrindo as UFs do MVP fiscal:

Filial SP (UF = SP)

Filial MG (UF = MG)

Filial RJ (UF = RJ)

Filial ES (UF = ES)

Cada filial deve possuir configurações fiscais mínimas para NFC-e (ambiente, certificado simulado, etc.).

Terminais

Para cada filial, criar pelo menos 1 terminal ativo, por exemplo:

PDV-01-SP

PDV-01-MG

PDV-01-RJ

PDV-01-ES

Usuários

Criar usuários padrão:

admin — perfil administrador interno.

supervisor — supervisão da filial.

operador — operador de caixa.

Associar usuários às filiais via UserFilial:

admin → acesso a todas as filiais.

supervisor → acesso a 1 ou mais filiais específicas.

operador → acesso a uma filial específica.

CFOP / NCM / Tabela Fiscal

Carregar um subconjunto realista de CFOP/NCM, suficiente para:

Operações de venda dentro do estado.

Operações interestaduais simples.

Devolução básica.

O subconjunto inicial deve contemplar as UFs: SP, MG, RJ, ES.
Ver detalhes em docs/dados/cfop_ncm_seed.md (separar a lista ou critério de seleção).

Catálogo de Produtos

Criar uma lista de produtos genéricos de varejo:

Exemplo:

PROD-001 — Produto teste 1 (vinculado a CFOP/NCM válidos).

PROD-002 — Produto teste 2.

Preços e categorias podem ser simples, o objetivo é ter fluxo fiscal funcional.

Clientes (opcional)

Criar alguns clientes genéricos:

Pessoa física (CPF mascarado).

Pessoa jurídica (CNPJ mascarado).

3.3. Execução
python manage.py migrate
python manage.py seed_dados --profile=dev


O comando deve ser idempotente: executar duas vezes não deve causar erro nem duplicação indevida.

4. Perfil qa
4.1. Objetivo

Fornecer uma massa de dados controlada e estável, voltada para testes automatizados (pytest) e manuais de QA, com foco em reproduzir cenários específicos.

4.2. Dados Criados

Tenant de QA

22345678000199 — Tenant QA

Filiais e UFs

Criar, no mínimo:

1 filial em SP (UF = SP).

1 filial em MG (UF = MG).

Podemos estender para RJ/ES conforme a evolução dos testes fiscais.

Terminais

1 terminal por filial, com nomes previsíveis (ex.: QA-PDV-SP, QA-PDV-MG).

Usuários

qa_admin

qa_operador

Com perfis e acessos bem definidos para cenários de teste.

CFOP / NCM / Tabela Fiscal

Carregar apenas os CFOP/NCM necessários para os cenários de teste automatizado, por exemplo:

CFOP de venda normal.

CFOP de devolução.

CFOP de operação interestadual (se houver teste cobrindo).

Cenários de Teste Pré-configurados (opcional)

Criar alguns registros que representam:

Pré-emissões de NFC-e já gravadas.

Reservas de número existentes.

Configurações fiscais específicas para testes de rejeição.

Isso facilita a escrita de testes de ponta a ponta sem precisar montar o cenário a cada teste.

4.3. Execução

Ambiente de QA / CI:

python manage.py migrate
python manage.py seed_dados --profile=qa
pytest


O seed de QA também deve ser idempotente e adequado para rodar em pipelines de CI.

5. Perfil demo
5.1. Objetivo

Fornecer uma massa de dados pensada para apresentações comerciais e treinamentos, com nomes amigáveis e dados visualmente agradáveis.

5.2. Dados Criados

Tenant Demo

32345678000199 — Tenant Demo (nome de fantasia mais comercial).

Filiais

Pelo menos 1 filial em SP.

Outras UFs podem ser adicionadas se forem úteis para demonstrações.

Terminais

1 ou mais terminais por filial, com nomes simples (CAIXA-01, CAIXA-02).

Usuários

demo_admin

demo_operador

Com credenciais e perfis adequados para demo.

Produtos

Produtos com nomes amigáveis e variados (ex.: Camiseta Básica, Calça Jeans, Tênis Esportivo).

Preços coerentes com varejo.

CFOP / NCM

Suficiente para permitir emissão de NFC-e demo (funcionalidade fiscal ativa ou em modo mock).

5.3. Execução
python manage.py migrate
python manage.py seed_dados --profile=demo

6. Considerações Multi-Tenant

Os seeds devem respeitar a arquitetura django-tenants:

Criação de Tenant e Domain no schema público.

Uso de schema_context(tenant.schema_name) para criar:

Filiais.

Terminais.

Usuários.

Tabelas de CFOP/NCM / produtos / clientes.

Exemplo conceitual:

from django_tenants.utils import schema_context

def _seed_tenant_dev():
    tenant = Tenant.objects.get_or_create(
        cnpj_raiz="12345678000199",
        defaults={"nome": "Tenant Dev Principal"},
    )[0]

    with schema_context(tenant.schema_name):
        # criar filiais, terminais, usuários, etc.
        ...

7. Boas Práticas e Regras

Idempotência

Sempre usar get_or_create ou checar existência antes de criar.

Nunca assumir banco vazio.

Dados Sensíveis

Não incluir dados reais de clientes ou empresas.

Para CFOP/NCM, usar códigos oficiais, mas sem vincular a dados de terceiros.

Separação de Ambientes

Nunca rodar seed_dados --profile=dev/qa/demo em produção.

Seeds de produção, se existirem, devem ser específicos e documentados em outro arquivo.

Integração com Makefile / Scripts

Recomenda-se adicionar atalhos, por exemplo:

seed-dev:
	python manage.py seed_dados --profile=dev

seed-qa:
	python manage.py seed_dados --profile=qa

seed-demo:
	python manage.py seed_dados --profile=demo

8. Próximos Passos

Implementar o comando seed_dados no backend, seguindo esta especificação.

Criar o documento docs/dados/cfop_ncm_seed.md detalhando quais CFOP/NCM serão carregados para SP, MG, RJ e ES.

Integrar a execução de seed_dados nos fluxos de:

Onboarding de dev (README / Makefile).

Ambiente de QA / CI (pipelines).
