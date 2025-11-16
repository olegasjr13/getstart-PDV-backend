# NGINX Reverse Proxy — GetStart PDV (Arquitetura de Produção)

## 1. Objetivo

Este documento define o **padrão oficial de configuração do NGINX** usado como *reverse proxy* do backend do GetStart PDV em ambiente de produção, contemplando:

- Segurança (TLS, headers, mitigação de ataques)
- Reverse proxy para o backend Django (Gunicorn)
- Timeouts fiscais (adequados para SEFAZ)
- Regras de compressão e caching
- Proteção de endpoints sensíveis
- Logs estruturados
- Compatibilidade com Railway, Docker, AWS e Kubernetes
- Padrão POS (aplicação rodando em app desktop/mobile, não navegador)

O NGINX é responsável por:

- Terminar TLS  
- Garantir segurança e otimização  
- Encaminhar requisições ao backend  
- Tratar timeouts de forma consistente com SEFAZ  

---

# 2. Arquitetura Geral

Fluxo simplificado:

```
[Cliente (App PDV)]
      ↓ HTTPS (NGINX)
[NGINX Reverse Proxy]
      ↓ HTTP interno
[Backend Django + Gunicorn]
      ↓
[PostgreSQL / Redis / ...]
      ↓
[SEFAZ (via clients por UF)]
```

O NGINX **não se comunica com SEFAZ**.  
Quem faz isso é o backend.

---

# 3. Requisitos do Proxy

### 3.1 Segurança

- TLS 1.2+ obrigatório  
- Ciphers modernos  
- HSTS (em produção)  
- Bloqueio de métodos não usados  
- Headers de segurança  
- Rate limit opcional  

### 3.2. Performance

- Keep-alive otimizado  
- Compressão gzip  
- Reuso de conexões com o backend  

### 3.3. Timeouts adequados para SEFAZ

A SEFAZ pode demorar até **30 segundos** em períodos de instabilidade.  
O NGINX deve suportar isso:

- `proxy_read_timeout 60s`
- `proxy_connect_timeout 15s`
- `proxy_send_timeout 60s`

---

# 4. Estrutura Final de Arquivos

Recomendado:

```
/etc/nginx/
    nginx.conf
    conf.d/
        pdv.conf
    ssl/
        fullchain.pem
        privkey.pem
```

Ou no Docker:

```
nginx/
 ├─ nginx.conf
 ├─ pdv.conf
 └─ ssl/
```

---

# 5. nginx.conf (arquivo principal)

A configuração principal deve ser mínima e direcionar para `conf.d/*.conf`:

```nginx
user  nginx;
worker_processes auto;

events {
    worker_connections 2048;
}

http {
    include       mime.types;
    default_type  application/octet-stream;

    sendfile        on;
    keepalive_timeout  65;

    gzip on;
    gzip_types text/plain text/css application/json application/javascript;

    include /etc/nginx/conf.d/*.conf;
}
```

---

# 6. pdv.conf — Reverse Proxy

Arquivo principal do proxy:

```nginx
server {
    listen 80;
    server_name _;

    # Redireciona tudo para HTTPS (produção)
    return 301 https://$host$request_uri;
}
```

E o servidor seguro:

```nginx
server {
    listen 443 ssl http2;
    server_name _;

    ssl_certificate     /etc/nginx/ssl/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/privkey.pem;

    # Configurações de segurança
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_session_cache shared:SSL:10m;

    # HSTS (apenas produção)
    add_header Strict-Transport-Security "max-age=63072000" always;

    # Headers de segurança adicionais
    add_header X-Frame-Options "DENY";
    add_header X-Content-Type-Options "nosniff";
    add_header X-XSS-Protection "1; mode=block";

    # Logs estruturados
    access_log /var/log/nginx/pdv_access.log;
    error_log  /var/log/nginx/pdv_error.log;

    client_max_body_size 20M;

    location / {
        proxy_pass http://backend:8000;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;

        # Timeouts compatíveis com SEFAZ
        proxy_connect_timeout 15s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;

        # Evita buffering em respostas longas (ex: logs ou XML)
        proxy_buffering off;
    }
}
```

---

# 7. Proteções Recomendadas

## 7.1. Bloqueio de métodos não usados

```nginx
if ($request_method !~ ^(GET|POST|OPTIONS)$) {
    return 405;
}
```

## 7.2. Rate Limit (opcional)

Para evitar abuso:

```nginx
limit_req_zone $binary_remote_addr zone=backend_limit:10m rate=10r/s;

location /api/ {
    limit_req zone=backend_limit burst=20;
}
```

---

# 8. Compatibilidade com Railway

No Railway, portas são dinâmicas.  
Use:

```nginx
listen ${PORT} ssl http2;
```

E backend:

```nginx
proxy_pass http://backend:8000;
```

Certificados são fornecidos pela plataforma.

---

# 9. Compatibilidade com Docker Compose

Exemplo de `docker-compose.yml`:

```yaml
services:
  nginx:
    image: nginx:alpine
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf
      - ./nginx/pdv.conf:/etc/nginx/conf.d/pdv.conf
      - ./nginx/ssl:/etc/nginx/ssl
    ports:
      - "80:80"
      - "443:443"
    depends_on:
      - backend
```

Backend exposto como:

```
backend:8000
```

---

# 10. Cabeçalhos Usados pelo Backend

O NGINX deve **propagar**:

- `X-Tenant-ID`
- `X-Filial-Id`
- `X-Terminal-Id`
- `Authorization`

Todos são obrigatórios para o fluxo fiscal.

Nada deve ser removido.

---

# 11. CORS

O PDV não roda via navegador → **CORS não é necessário**.

Mas, se necessário para ambiente web:

```nginx
add_header Access-Control-Allow-Origin "*";
add_header Access-Control-Allow-Headers "*";
add_header Access-Control-Allow-Methods "GET, POST, OPTIONS";
```

---

# 12. Healthchecks

Permitir acesso aos endpoints:

```nginx
location /health/liveness {
    proxy_pass http://backend:8000/health/liveness;
}

location /health/readiness {
    proxy_pass http://backend:8000/health/readiness;
}
```

---

# 13. Logs Estruturados

Formato recomendado:

```nginx
log_format json_combined escape=json
  '{'
  '"time":"$time_iso8601",'
  '"remote_addr":"$remote_addr",'
  '"method":"$request_method",'
  '"uri":"$request_uri",'
  '"status":$status,'
  '"body_bytes_sent":$body_bytes_sent,'
  '"referer":"$http_referer",'
  '"user_agent":"$http_user_agent"'
  '}';
```

Uso:

```nginx
access_log /var/log/nginx/pdv_access.log json_combined;
```

---

# 14. Testes e Validações

Antes de liberar para produção:

### 14.1. Testar syntax:
```
nginx -t
```

### 14.2. Testar rotas:
```
curl -I https://api.seudominio.com/health/liveness
```

### 14.3. Testar timeouts SEFAZ:
Simular demora usando:

```
proxy_read_timeout 60s;
```

### 14.4. Testar TLS:
```
curl -vI https://api.seudominio.com
```

---

# 15. Conclusão

Este é o padrão **oficial e recomendado** de configuração NGINX para o GetStart PDV:

- Seguro  
- Compatível com necessidades fiscais  
- Tolerante a delays da SEFAZ  
- Alinhado com Docker/Railway  
- Otimizado para alto volume de requests do PDV  

Qualquer ajuste ou extensão deve seguir este documento como base.
