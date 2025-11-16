# Hardening do Backend — GetStart PDV

## 1. Objetivo

Este documento define os **padrões oficiais de segurança (hardening)** para o backend do GetStart PDV, alinhados ao cenário real:

- PDV rodando em **aplicativo** (desktop/mobile), NÃO navegador.
- Emissão fiscal (NFC-e) com certificação A1.
- Multi-tenant isolado por schema.
- Arquitetura moderna com API REST + JWT Bearer.
- Segurança robusta para ambientes dev, QA e produção.
- Princípios semelhantes ao POS Controle.

Este documento é obrigatório para desenvolvimento, QA, DevOps e auditoria.

---

# 2. Super Resumo — Decisões de Segurança

| Item | Decisão | Justificativa |
|------|---------|----------------|
| Autenticação | **JWT Bearer em header** | App POS → sem XSS → seguro e simples |
| Refresh token | **Opcional**, mas recomendado | Mantém sessão longa sem risco de XSS |
| Certificados A1 | **Criptografados + acesso controlado** | Item mais sensível do PDV |
| Ambiente | **sem cookies, sem sessões web** | 100% app |
| Multi-tenant | **Isolamento por schema** | Evita vazamento entre empresas |
| Logs | **Sem dados sensíveis** | Compliance |
| Auditoria | **Obrigatória** | Requisitos fiscais |
| Limpeza/Expiração | Tokens curtos + refresh | Segurança extra |

---

# 3. Autenticação e Autorização

## 3.1. Autenticação via JWT Bearer

O PDV (app) faz requisições assim:

```
Authorization: Bearer <access_token>
```

**Por que é seguro aqui?**
- Não existe navegador → sem XSS.
- O app controla o armazenamento do token com segurança.
- Menos complexidade que cookies HttpOnly.
- 100% compatível com POS Controle.

## 3.2. Regras obrigatórias para JWT

### Access token
- Validade: **5 a 10 minutos**
- Contém:
  - `tenant_id`
  - `user_id`
  - `perfis`
  - `filial_id` (opcional)
  - `terminal_id` (opcional)

### Refresh token
- Validade sugerida: **7 dias**
- Uso permitido apenas em:
  - app PDV
  - endpoints seguros

### 3.3. Header obrigatório do tenant
Toda requisição do PDV deve enviar:

```
X-Tenant-ID: <cnpj_raiz>
```

Backend resolve schema e valida.

---

# 4. Proteção dos Certificados A1

**Atenção**: este é o ponto mais sensível de todo o PDV.

### 4.1. Regras obrigatórias

- Certificado `.pfx` deve ser armazenado **criptografado** no banco ou sistema seguro.
- Senha do PFX também deve estar **criptografada**.
- Nunca gravar em disco “aberto”.
- Conversão para PEM ocorre **somente em memória**.
- Remover buffer da memória após uso.
- Não logar:
  - PEM
  - Senha
  - Conteúdo
  - Dados do certificado

### 4.2. Permissões restritas

Somente papéis administrativos podem:

- Cadastrar certificado
- Alterar
- Remover
- Ativar ambiente produção

---

# 5. Proteção Fiscal (NFC-e)

A emissão fiscal segue:

```
pré-emissão → geração XML → assinatura → envio SEFAZ → auditoria → retorno
```

### 5.1. Proteções obrigatórias

- Validar ambiente (`mock/homolog/producao`) em cada requisição.
- Filial deve estar ativa.
- Terminal deve estar ativo.
- Certificado deve estar válido.
- Numeração protegida por **idempotência via request_id**.
- Rejeições da SEFAZ → sempre registradas.

### 5.2. Anti-fraude de número

- Bloquear reemissão com mesmo número/série/terminal.
- Registrar tentativa suspeita no log.

---

# 6. Segurança Multi-Tenant

### 6.1. Isolamento por schema

Regras:

1. Cada tenant tem **seu próprio schema**.
2. Nunca misturar dados entre schemas.
3. Toda requisição passa por middleware que:
   - resolve tenant,
   - troca para schema correto,
   - valida acesso.

### 6.2. Proteções

- Negar acesso caso tenant esteja INATIVO.
- Logar tentativa suspeita: `tenant_inactive_access_blocked`.

---

# 7. Controle de Acesso

### 7.1. RBAC (Role-Based Access Control)

Perfis recomendados:

- `ADMIN`
- `SUPERVISOR`
- `OPERADOR`

### 7.2. Princípio do menor privilégio

Operador:

- Emite NFC-e
- Fecha caixa
- Consulta venda

Supervisor:

- Cancela documento
- Movimentação avançada

Admin:

- Configurações fiscais
- Certificados
- Ambientes

---

# 8. Proteção de Endpoints

### 8.1. Endpoints críticos

- `/api/fiscal/nfce/*`
- `/api/certificados/*`
- `/api/filiais/*`

Devem exigir:

- Autorização JWT
- Acesso ao tenant
- Papel suficiente
- Logs detalhados

### 8.2. Endpoints de emissão

Rejeitar automaticamente:

- Filial sem ambiente definido
- Certificado vencido

---

# 9. Segurança de Logs

**Nunca** logar:

- Senha do banco
- Senha do certificado
- XML completo com dados sensíveis do consumidor
- Dados de cartão
- Tokens JWT

Permitido logar com máscara:

- CPF/CNPJ
- Razão social
- XML resumido (quando útil)

---

# 10. Erros e Exceções

### 10.1. Respostas padronizadas
Todos erros devem seguir:

```
{
  "error": "FISCAL_4001",
  "message": "Certificado inválido"
}
```

### 10.2. Bloqueio de stack trace:

- Nunca retornar trace no response.
- Usar Sentry para capturar internamente.

---

# 11. Segurança de Ambientes

### DEV
- Ambiente MOCK obrigatório.
- Certificados fictícios.
- Tokens longos permitidos.

### QA
- Ambiente MOCK ou HOMOLOG.
- Auditoria recomendada.
- Mais logs para debugging.

### PRODUÇÃO
- Certificado A1 real.
- Auditoria OBRIGATÓRIA.
- Logs mínimos.
- Sem endpoints de debug.

---

# 12. Segurança de Infra (Backend)

### 12.1. Recomendações

- Rodar sempre em HTTPS.
- TLS mínimo 1.2 (preferível 1.3).
- Firewall bloqueando portas não usadas.
- Rate-limit opcional por tenant.
- Conteiner seguro:
  - rootless
  - read-only filesystem quando possível
- Healthcheck separado do `/api`.

---

# 13. Segurança no Processo de Build / Deploy

- Variáveis sensíveis somente em ENV com criptografia.
- Build de produção sem pacotes desnecessários.
- CI/CD sem tokens de acesso expostos.

---

# 14. Resumo Final das Regras Críticas

1. JWT Bearer → seguro em app POS.
2. Certificados A1 → criptografados, nunca no disco.
3. Auditoria → obrigatória na emissão NFC-e.
4. Logs → sem dados sensíveis.
5. Multi-tenant → isolado por schema.
6. Ambiente (`mock/homolog/producao`) → definido na filial.
7. PDV → nunca controla ambiente.
8. Erros → padronizados.
9. Segurança aplicável a dev, QA e produção.

---

# 15. Evolução Planejada

- Assinatura em HSM/Token em produção (futuro)
- Múltiplos certificados por filial
- Controle granular de permissões
- Segregação de rotas administrativas
- Hardening de comunicações com SEFAZ

Qualquer alteração estrutural de segurança deve atualizar este documento.
