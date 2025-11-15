# conftest.py
import os
import pytest
from django.conf import settings
from django.db import connections, close_old_connections

@pytest.fixture(autouse=True, scope="function")
def _force_test_tuning(settings):
    """
    Ajustes de teste para evitar conexões persistentes e facilitar teardown.
    """
    # Evita conexões persistentes em qualquer cenário
    settings.DATABASES["default"]["CONN_MAX_AGE"] = 0
    # Garante schema public durante criação de tenant/domain
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

    # Garante que conexões "herdadas" estejam limpas
    close_old_connections()
    yield
    # Fecha qualquer conexão que possa ter ficado aberta (inclusive por threads)
    for conn in connections.all():
        try:
            conn.close()
        except Exception:
            pass
    # Previne conexões zumbis entre testes
    close_old_connections()
