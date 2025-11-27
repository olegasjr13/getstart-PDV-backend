# fiscal/tests/fixtures/client_host.py
import pytest
from rest_framework.test import APIClient

@pytest.fixture
def client_host():
    """
    APIClient com HTTP_HOST 'cliente-demo.localhost' para a TenantMainMiddleware
    resolver o tenant corretamente durante os testes.
    """
    def _make(host: str = "cliente-demo.localhost") -> APIClient:
        c = APIClient()
        c.defaults["HTTP_HOST"] = host
        return c
    return _make
