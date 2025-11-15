# Padrões de Desenvolvimento Backend — GetStart PDV

## 1. Objetivo
Este documento define os padrões oficiais de desenvolvimento do backend GetStart PDV, garantindo consistência entre os apps, previsibilidade de comportamento e facilidade de manutenção. Os padrões aqui descritos refletem a forma como o backend **já está construído**, especialmente o módulo `fiscal`, e devem ser seguidos por todos os novos desenvolvimentos.

## 2. Estrutura de Apps
Cada app deve conter:
- models.py
- serializers.py
- views.py
- services/
- tests/
- urls.py (quando aplicável)

## 3. Views finas, Services gordos
Views nunca devem conter regra de negócio.
Exemplo correto:
```
result = NfcePreEmissaoService(tenant).criar_pre_emissao(...)
return Response(result)
```

## 4. Serializers
Responsáveis apenas por:
- validação de entrada
- conversão de tipos
- mapeamento simples de modelos

Não devem conter regras fiscais ou cálculos.

## 5. Services
Toda regra de negócio vai aqui.
Exemplos das responsabilidades:
- reserva de numeração
- validações fiscais
- cálculos
- integração com serviços externos
- garantia de idempotência

Estrutura recomendada:
```
class NomeService:
    def __init__(self, tenant):
        self.tenant = tenant

    def executar(self, payload):
        self._validar(payload)
        self._processar(payload)
        return self._gerar_resultado()
```

## 6. Selectors (opcional)
Consultas complexas ou reutilizáveis devem ir em selectors.py.

## 7. Padrões de Nomeação
- Services: `XyzService`
- Selectors: `XyzSelector`
- Views: `XyzViewSet` ou `XyzAPIView`
- Testes: `test_xyz.py`

## 8. Erros
Erros devem usar códigos padronizados conforme `docs/api/guia_erros_excecoes.md`.

## 9. Logging
Todos os services devem registrar:
- início da operação
- resultado
- erros
Veja `docs/observabilidade/padroes_logs_backend.md`.

## 10. Multi-tenant
Nunca acessar dados sem contexto do tenant.
Padrao:
```
with schema_context(tenant.schema_name):
    ...
```

## 11. Testes
Cada nova feature deve incluir:
- teste unitário do service
- teste de integração da view
- teste de idempotência se aplicável
