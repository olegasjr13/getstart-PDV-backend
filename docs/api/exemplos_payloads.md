# GetStart PDV — Exemplos de Payloads

## 1. Login

### Request

```json
POST /api/v1/auth/login
{
  "username": "operador1",
  "password": "senha123",
  "terminal_id": "7b0f8c95-4ae4-4e35-9c18-0d7cfdaf0001"
}
```

### Response

```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "user": {
    "id": 10,
    "perfil": "OPERADOR",
    "filial_id": "f5bb9e8e-5c3e-4b09-a1a3-000000000001",
    "terminal_id": "7b0f8c95-4ae4-4e35-9c18-0d7cfdaf0001"
  }
}
```

---

## 2. Reserva de Numeração NFC-e

### Request

```json
POST /api/v1/fiscal/nfce/reservar-numero
Headers:
  Authorization: Bearer <access>
  X-Tenant-ID: 12345678000199

Body:
{
  "terminal_id": "7b0f8c95-4ae4-4e35-9c18-0d7cfdaf0001",
  "serie": 1,
  "request_id": "4d6c7a2a-5a27-4bf0-9b9e-3bf500000001"
}
```

### Response

```json
{
  "numero": 123,
  "serie": 1,
  "filial_id": "f5bb9e8e-5c3e-4b09-a1a3-000000000001",
  "terminal_id": "7b0f8c95-4ae4-4e35-9c18-0d7cfdaf0001",
  "request_id": "4d6c7a2a-5a27-4bf0-9b9e-3bf500000001",
  "reserved_at": "2025-07-01T12:34:56Z"
}
```

---

## 3. Pré-Emissão

### Request

```json
POST /api/v1/fiscal/nfce/pre-emissao
Headers:
  Authorization: Bearer <access>
  X-Tenant-ID: 12345678000199

Body:
{
  "request_id": "4d6c7a2a-5a27-4bf0-9b9e-3bf500000001",
  "payload": {
    "cliente": {
      "cpf": "12345678909",
      "nome": "Consumidor Final"
    },
    "itens": [
      {
        "produto_id": "11111111-2222-3333-4444-555555555555",
        "descricao": "REFRIGERANTE LATA",
        "qtd": 2,
        "unidade": "UN",
        "preco_unitario": 5.00,
        "desconto": 0.00,
        "total": 10.00
      }
    ],
    "totais": {
      "valor_itens": 10.00,
      "descontos": 0.00,
      "acrescimos": 0.00,
      "valor_nfce": 10.00
    },
    "pagamentos": [
      {
        "forma": "DINHEIRO",
        "valor": 20.00
      }
    ],
    "troco": 10.00
  }
}
```

### Response

```json
{
  "numero": 123,
  "serie": 1,
  "filial_id": "f5bb9e8e-5c3e-4b09-a1a3-000000000001",
  "terminal_id": "7b0f8c95-4ae4-4e35-9c18-0d7cfdaf0001",
  "request_id": "4d6c7a2a-5a27-4bf0-9b9e-3bf500000001",
  "payload": { "...": "igual ao enviado" },
  "created_at": "2025-07-01T12:35:10Z"
}
```

---

## 4. Emissão (Mock)

### Request

```json
POST /api/v1/fiscal/nfce/emissao
Headers:
  Authorization: Bearer <access>
  X-Tenant-ID: 12345678000199

Body:
{
  "request_id": "4d6c7a2a-5a27-4bf0-9b9e-3bf500000001"
}
```

### Response

```json
{
  "numero": 123,
  "serie": 1,
  "filial_id": "f5bb9e8e-5c3e-4b09-a1a3-000000000001",
  "terminal_id": "7b0f8c95-4ae4-4e35-9c18-0d7cfdaf0001",
  "chave": "35250712345678000199550010000001231000001230",
  "xml": "<NFe>...</NFe>",
  "danfe_base64": "iVBORw0KGgoAAAANSUhEUgAA...",
  "status": "AUTORIZADA"
}
```

---

## 5. Cancelamento

### Request

```json
POST /api/v1/fiscal/nfce/cancelar
{
  "chave": "35250712345678000199550010000001231000001230",
  "justificativa": "Erro de digitação do valor"
}
```

### Response

```json
{
  "chave": "35250712345678000199550010000001231000001230",
  "status": "CANCELADA",
  "protocolo_cancelamento": "135250000000000",
  "data_hora": "2025-07-01T13:00:00Z"
}
```
