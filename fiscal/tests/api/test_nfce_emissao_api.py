# fiscal/tests/api/test_nfce_emissao_api.py

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
from fiscal.models import (
    NfceNumeroReserva,
    NfcePreEmissao,
    NfceDocumento,
    NfceAuditoria,
)



@override_settings(
    ROOT_URLCONF="config.urls",
    ALLOWED_HOSTS=["*", TENANT_HOST, "testserver"],
)
@pytest.mark.django_db(transaction=True)
def test_emitir_nfce_api_happy_path():
    """
    Cenário feliz de emissão NFC-e via API:

      1. Cria user, filial, terminal e vínculo user↔filial.
      2. Cria reserva de número (NfceNumeroReserva).
      3. Cria NfcePreEmissao para esse request_id.
      4. Chama POST /api/v1/fiscal/nfce/emitir/ com request_id.
      5. Valida:
         - HTTP 200
         - Corpo com chave_acesso, status, numero, serie
         - NfceDocumento criado
         - NfceAuditoria criada
    """

    _bootstrap_public_tenant_and_domain()
    User = get_user_model()

    with schema_context(TENANT_SCHEMA):
        user = User.objects.create_user(username="api-oper", password="123456")

        filial = Filial.objects.create(
            cnpj="11111111000111",
            nome_fantasia="Filial API",
            uf="SP",
            csc_id="ID",
            csc_token="TK",
            ambiente="homolog",
        )
        _ensure_a1_valid(filial)

        term = Terminal.objects.create(
            identificador="T-API-01",
            filial_id=filial.id,
            serie=1,
            numero_atual=1,
            ativo=True,
        )

        # vínculo user ↔ filial
        user.userfilial_set.create(filial_id=filial.id)

        # reserva de número
        reserva = NfceNumeroReserva.objects.create(
            terminal_id=term.id,
            filial_id=filial.id,
            serie=term.serie,
            numero=term.numero_atual,
            request_id=uuid.uuid4(),
        )

        # pré-emissão
        pre = NfcePreEmissao.objects.create(
            filial_id=filial.id,
            terminal_id=term.id,
            numero=reserva.numero,
            serie=reserva.serie,
            request_id=reserva.request_id,
            payload={
                "itens": [],
                "pagamentos": [],
                "cliente": None,
            },
        )

        client = _make_client_jwt(user)

        resp = client.post(
            "/api/v1/fiscal/nfce/emitir/",
            data={"request_id": str(pre.request_id)},
            format="json",
        )

        assert resp.status_code == 200, resp.content

        data = resp.json()
        assert data["status"] == "autorizada"
        assert data["numero"] == pre.numero
        assert data["serie"] == pre.serie
        assert data["filial_id"] == str(filial.id)
        assert data["terminal_id"] == str(term.id)
        assert data["chave_acesso"].startswith("NFe")

        # documento persistido
        docs = NfceDocumento.objects.filter(request_id=pre.request_id)
        assert docs.count() == 1
        doc = docs.first()
        assert doc.status == "autorizada"

        # auditoria persistida
        audits = NfceAuditoria.objects.filter(request_id=pre.request_id)
        assert audits.count() == 1
