import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test.utils import override_settings
from django_tenants.utils import schema_context

from filial.models.filial_models import Filial
from fiscal.tests.test_nfce_a1_edge_cases import _bootstrap_public_tenant_and_domain
from fiscal.tests.test_nfce_atomicidade_rollback import TENANT_SCHEMA
from fiscal.tests.test_nfce_auditoria_logs import TENANT_HOST, _make_client_jwt
from fiscal.tests.test_nfce_rate_limit_user_throttle import _ensure_a1_valid
from terminal.models.terminal_models import Terminal
from fiscal.models import NfceInutilizacao




@override_settings(
    ROOT_URLCONF="config.urls",
    ALLOWED_HOSTS=["*", TENANT_HOST, "testserver"],
)
@pytest.mark.django_db(transaction=True)
def test_inutilizar_faixa_api_happy_path():
    """
    Cenário feliz de inutilização via API.
    """

    _bootstrap_public_tenant_and_domain()
    User = get_user_model()

    with schema_context(TENANT_SCHEMA):
        user = User.objects.create_user(username="api-inut", password="123456")

        filial = Filial.objects.create(
            cnpj="55555555000155",
            nome_fantasia="Filial API Inut",
            uf="SP",
            csc_id="ID",
            csc_token="TK",
            ambiente="homolog",
        )
        _ensure_a1_valid(filial)

        term = Terminal.objects.create(
            identificador="T-API-INUT-01",
            filial_id=filial.id,
            serie=1,
            numero_atual=1,
            ativo=True,
        )

        user.userfilial_set.create(filial_id=filial.id)

        req_id = uuid.uuid4()

        client = _make_client_jwt(user)

        resp = client.post(
            "/api/v1/fiscal/nfce/inutilizar/",
            data={
                "filial_id": str(filial.id),
                "serie": term.serie,
                "numero_inicial": 50,
                "numero_final": 60,
                "motivo": "Faixa reservada, mas nunca utilizada.",
                "request_id": str(req_id),
            },
            format="json",
        )

        assert resp.status_code == 200, resp.content
        data = resp.json()

        assert data["status"] == "inutilizada"
        assert data["numero_inicial"] == 50
        assert data["numero_final"] == 60
        assert data["filial_id"] == str(filial.id)

        inutil = NfceInutilizacao.objects.get(request_id=req_id)
        assert inutil.status == "inutilizada"


@override_settings(
    ROOT_URLCONF="config.urls",
    ALLOWED_HOSTS=["*", TENANT_HOST, "testserver"],
)
@pytest.mark.django_db(transaction=True)
def test_inutilizar_faixa_api_sem_autenticacao():
    """
    Chamada sem autenticação deve ser rejeitada com 401/403.
    """

    _bootstrap_public_tenant_and_domain()

    from rest_framework.test import APIClient

    client = APIClient()

    resp = client.post(
        "/api/v1/fiscal/nfce/inutilizar/",
        data={
            "filial_id": "00000000-0000-0000-0000-000000000000",
            "serie": 1,
            "numero_inicial": 1,
            "numero_final": 2,
            "motivo": "Tentativa sem autenticação.",
            "request_id": str(uuid.uuid4()),
        },
        format="json",
        HTTP_HOST=TENANT_HOST,
    )

    assert resp.status_code in (401, 403)
