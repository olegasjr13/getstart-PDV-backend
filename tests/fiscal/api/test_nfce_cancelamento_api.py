import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test.utils import override_settings
from django_tenants.utils import schema_context

from filial.models.filial_models import Filial
from fiscal.tests.test_nfce_a1_edge_cases import _bootstrap_public_tenant_and_domain, _make_client_jwt
from fiscal.tests.test_nfce_atomicidade_rollback import TENANT_SCHEMA
from fiscal.tests.test_nfce_auditoria_logs import TENANT_HOST
from fiscal.tests.test_nfce_rate_limit_user_throttle import _ensure_a1_valid
from terminal.models.terminal_models import Terminal
from fiscal.models import NfceDocumento




@override_settings(
    ROOT_URLCONF="config.urls",
    ALLOWED_HOSTS=["*", TENANT_HOST, "testserver"],
)
@pytest.mark.django_db(transaction=True)
def test_cancelar_nfce_api_happy_path():
    """
    Cenário feliz de cancelamento NFC-e via API.
    """

    _bootstrap_public_tenant_and_domain()
    User = get_user_model()

    with schema_context(TENANT_SCHEMA):
        user = User.objects.create_user(username="api-canc", password="123456")

        filial = Filial.objects.create(
            cnpj="11111111000111",
            nome_fantasia="Filial API Canc",
            uf="SP",
            csc_id="ID",
            csc_token="TK",
            ambiente="homolog",
        )
        _ensure_a1_valid(filial)

        term = Terminal.objects.create(
            identificador="T-API-CANC-01",
            filial_id=filial.id,
            serie=1,
            numero_atual=1,
            ativo=True,
        )

        user.userfilial_set.create(filial_id=filial.id)

        doc = NfceDocumento.objects.create(
            request_id=uuid.uuid4(),
            filial=filial,
            terminal=term,
            numero=1,
            serie=1,
            chave_acesso="NFe" + "3" * 44,
            protocolo="",
            status="autorizada",
            mensagem_sefaz="Autorizado o uso da NFC-e.",
        )

        client = _make_client_jwt(user)

        resp = client.post(
            "/api/v1/fiscal/nfce/cancelar/",
            data={
                "chave_acesso": doc.chave_acesso,
                "motivo": "Cancelamento via API para testes.",
            },
            format="json",
        )

        assert resp.status_code == 200, resp.content
        data = resp.json()

        assert data["status"] == "cancelada"
        assert data["chave_acesso"] == doc.chave_acesso
        assert data["numero"] == doc.numero
        assert data["serie"] == doc.serie

        doc.refresh_from_db()
        assert doc.status == "cancelada"
        assert doc.protocolo.startswith("CANCEL-")


@override_settings(
    ROOT_URLCONF="config.urls",
    ALLOWED_HOSTS=["*", TENANT_HOST, "testserver"],
)
@pytest.mark.django_db(transaction=True)
def test_cancelar_nfce_api_sem_autenticacao():
    """
    A chamada sem JWT deve ser rejeitada com 401/403.
    Mesmo host do tenant, mas sem credenciais.
    """

    _bootstrap_public_tenant_and_domain()

    from rest_framework.test import APIClient

    client = APIClient()

    resp = client.post(
        "/api/v1/fiscal/nfce/cancelar/",
        data={
            "chave_acesso": "NFe" + "0" * 44,
            "motivo": "Tentativa sem autenticação.",
        },
        format="json",
        HTTP_HOST=TENANT_HOST,
    )

    assert resp.status_code in (401, 403)
