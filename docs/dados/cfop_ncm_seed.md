# Seed de CFOP e NCM — GetStart PDV

## 1. Objetivo

Este documento define o **subconjunto inicial de CFOP e NCM** que será carregado pelos scripts de seed de dados do GetStart PDV, com foco em:

- Permitir testes fiscais consistentes em **SP, MG, RJ e ES**.
- Cobrir os cenários mais comuns de **venda varejo**, **devolução** e **operações interestaduais simples**.
- Manter a massa de dados **enxuta e previsível**, sem tentar replicar toda a tabela fiscal oficial.

> **Importante:** esta lista não substitui a tabela fiscal oficial. Ela é um **recorte mínimo** voltado a desenvolvimento, QA e ambientes de demonstração.

---

## 2. Escopo

### 2.1. Unidades Federativas

Os seeds de CFOP/NCM devem atender, inicialmente, às seguintes UFs:

- **SP** — São Paulo  
- **MG** — Minas Gerais  
- **RJ** — Rio de Janeiro  
- **ES** — Espírito Santo  

Do ponto de vista de **CFOP/NCM**, o seed será o mesmo para todas as UFs.  
Diferenças de regras de ICMS, ST, etc. serão tratadas em configurações fiscais específicas por UF/filial, fora deste documento.

### 2.2. Perfis de Seed

Os perfis definidos em `scripts_seed_dados.md` utilizam este documento como base:

- `dev` → utiliza **todos** os CFOP/NCM listados aqui.
- `qa` → pode utilizar um **subconjunto** específico (definido abaixo).
- `demo` → utiliza apenas o conjunto necessário para cenários de apresentação.

---

## 3. CFOP — Conjunto Inicial

Abaixo, a proposta de CFOP mínimos a serem carregados, focados em operações de **saída de mercadorias** mais frequentes no varejo.

> Regra geral:  
> - CFOP iniciando em **5.xxx** — operações dentro do estado.  
> - CFOP iniciando em **6.xxx** — operações interestaduais.  

### 3.1. Vendas Internas (dentro do estado)

| CFOP  | Descrição resumida                                  | Uso principal                             |
|-------|-----------------------------------------------------|-------------------------------------------|
| 5102  | Venda de mercadoria adquirida de terceiros          | Venda varejo normal dentro do estado      |
| 5101  | Venda de produção do estabelecimento                | Quando a filial fabrica/industrializa     |
| 5403  | Venda de mercadoria adquirida de terceiros c/ ST    | Venda com Substituição Tributária         |
| 5405  | Venda de mercadoria recebida anteriormente c/ ST    | Revenda de produto já tributado por ST    |

Na prática do PDV, o mais utilizado será **5102** (varejo comum) e **5403/5405** quando envolver ST.

### 3.2. Vendas Interestaduais

| CFOP  | Descrição resumida                                                | Uso principal                               |
|-------|-------------------------------------------------------------------|---------------------------------------------|
| 6102  | Venda de mercadoria adquirida de terceiros para não contribuinte  | Venda interestadual para consumidor final   |
| 6101  | Venda de produção do estabelecimento                              | Venda interestadual de produção própria     |
| 6403  | Venda de mercadoria adquirida de terceiros c/ ST                  | Venda interestadual c/ ST (quando aplicável)|

Inicialmente, o seed não precisa cobrir todos os cenários complexos de DIFAL, mas ter esses CFOP permite montar cenários básicos de venda interestadual.

### 3.3. Devoluções

| CFOP  | Descrição resumida                                      | Uso principal                          |
|-------|---------------------------------------------------------|----------------------------------------|
| 5202  | Devolução de compra para comercialização               | Devolução interna de compra            |
| 5201  | Devolução de compra para industrialização              | Quando houver cenário de indústria     |
| 6202  | Devolução de compra para comercialização (interestadual)| Devolução interestadual de compra     |
| 6201  | Devolução de compra para industrialização (interestadual)| Cenários específicos de indústria   |

Dependendo da evolução dos fluxos de devolução, novos CFOP poderão ser adicionados.

### 3.4. CFOP para testes específicos (opcional)

Se necessário, poderemos incluir CFOPs adicionais para:

- Bonificação.
- Remessa para conserto.
- Operações simbólicas.

Esses CFOPs não entram no seed inicial, mas o documento deve ser atualizado conforme o time fiscal definir novos cenários.

---

## 4. NCM — Conjunto Inicial

O seed deve carregar um conjunto **enxuto** de NCMs, suficientemente variado para representar categorias típicas de varejo.

### 4.1. NCMs sugeridos

| NCM       | Descrição resumida                         | Uso sugerido                               |
|-----------|--------------------------------------------|--------------------------------------------|
| 6109.10.00| Camisetas de malha de algodão              | Vestuário básico (moda)                    |
| 6203.42.00| Calças de algodão                          | Vestuário (calças)                         |
| 6402.19.00| Calçados (sola de borracha/plástico)       | Calçados em geral                          |
| 8517.12.31| Telefones celulares                        | Eletrônicos (smartphones)                  |
| 8471.30.12| Laptops/notebooks                          | Eletrônicos de informática                 |
| 2202.10.00| Refrigerantes                              | Bebidas não alcoólicas                     |
| 3004.90.99| Medicamentos de uso humano (genérico)      | Farmácia (quando aplicável)                |
| 3924.90.00| Artigos domésticos de plástico             | Utilidades domésticas                       |
| 8212.10.20| Aparelhos de barbear                       | Higiene pessoal                             |
| 3304.99.90| Produtos de beleza e maquilagem            | Cosméticos                                 |

> OBS: As descrições aqui são **resumidas** apenas para entendimento interno.  
> As descrições formais e parametrizações fiscais (alíquota, CST, CSOSN, ST, etc.) devem ser definidas pelas regras fiscais do sistema.

### 4.2. Associação Produto ↔ NCM

Nos seeds de produtos:

- Cada produto deve apontar para um NCM **coerente** com sua descrição.
- Para fins de teste, não é necessário uma cobertura perfeita da legislação, mas:
  - Evitar combinações absurdas (ex.: celular com NCM de bebida).
  - Preparar pelo menos:
    - 2–3 produtos de vestuário.
    - 2–3 produtos eletrônicos.
    - 1–2 produtos de consumo rápido (bebida, higiene).

---

## 5. Uso por Perfil de Seed

### 5.1. Perfil `dev`

- Carregar **todos os CFOP** desta lista.
- Carregar **todos os NCM** desta lista.
- Permitir flexibilidade para o desenvolvedor criar produtos de teste adicionais, reutilizando esses CFOP/NCM.

### 5.2. Perfil `qa`

- Carregar apenas o **subconjunto necessário** para os cenários de teste automatizado.

Exemplo (sugestão para primeira versão):

- CFOP: `5102`, `5403`, `6102`, `5202`.
- NCM: `6109.10.00`, `8517.12.31`, `2202.10.00`.

Os testes devem documentar claramente quais CFOP/NCM estão sendo usados, para facilitar manutenção.

### 5.3. Perfil `demo`

- Carregar apenas o mínimo necessário para os produtos de demonstração:

- CFOP: `5102` (venda interna varejo).
- Opcionalmente: `5403` quando se quiser ilustrar ST.
- NCM: escolher 3–5 NCM que representem as categorias de produto usadas na demo.

---

## 6. Implementação no Script de Seed

O comando `seed_dados` deve:

1. Ter uma função responsável por criar/atualizar a **tabela de CFOP** (se existir).
2. Ter uma função responsável por criar/atualizar a **tabela de NCM** (se existir).
3. Respeitar o perfil (`dev`, `qa`, `demo`) para definir quais CFOP/NCM serão inseridos.
4. Ser **idempotente**, usando `get_or_create` ou lógica equivalente.

Pseudo-exemplo:

```python
def seed_cfop(profile: str):
    base_cfops = [
        {"codigo": "5102", "descricao": "Venda de mercadoria adquirida de terceiros"},
        {"codigo": "5403", "descricao": "Venda de mercadoria adquirida de terceiros com ST"},
        {"codigo": "6102", "descricao": "Venda de mercadoria adquirida de terceiros - fora do estado"},
        {"codigo": "5202", "descricao": "Devolução de compra para comercialização"},
        ...
    ]

    # Filtrar conforme o profile, se necessário
    cfops = filtrar_cfops_por_profile(base_cfops, profile)

    for item in cfops:
        Cfop.objects.update_or_create(
            codigo=item["codigo"],
            defaults={"descricao": item["descricao"]},
        )
O mesmo vale para NCM.

7. Evolução da Tabela

Conforme o projeto evoluir:

Novos CFOP/NCM podem ser adicionados ao seed.

Este documento deve ser atualizado sempre que:

Novos cenários fiscais forem implementados.

Novos testes exigirem CFOP/NCM específicos.

O time fiscal solicitar cobertura adicional.

Regra de ouro:

Nunca incluir CFOP/NCM “aleatórios”.
Toda inclusão deve ter um motivo claro (cenário de negócio ou teste).
