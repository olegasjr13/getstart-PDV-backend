import uuid

import pytest
from django.contrib.auth import get_user_model
from django_tenants.utils import schema_context

from filial.models.filial_models import Filial
from fiscal.tests.test_nfce_atomicidade_rollback import TENANT_SCHEMA, _bootstrap_public_tenant_and_domain
from fiscal.tests.test_nfce_auditoria_logs import _ensure_a1_valid
from terminal.models.terminal_models import Terminal
from fiscal.models import NfceDocumento
from fiscal.services.cancelamento_service import cancelar_nfce




@pytest.mark.django_db(transaction=True)
def test_cancelar_nfce_happy_path():
    """
    Cancela uma NFC-e autorizada com sucesso.
    """

    _bootstrap_public_tenant_and_domain()
    User = get_user_model()

    with schema_context(TENANT_SCHEMA):
        user = User.objects.create_user(username="oper-canc", password="123456")

        filial = Filial.objects.create(
            cnpj="11111111000111",
            nome_fantasia="Filial Canc",
            uf="SP",
            csc_id="ID",
            csc_token="TK",
            ambiente="homolog",
        )
        _ensure_a1_valid(filial)

        term = Terminal.objects.create(
            identificador="T-CANC-01",
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
            chave_acesso="NFe" + "1" * 44,
            protocolo="",
            status="autorizada",
            mensagem_sefaz="Autorizado o uso da NFC-e.",
        )

        result = cancelar_nfce(
            user=user,
            chave_acesso=doc.chave_acesso,
            filial_id=None,
            numero=None,
            serie=None,
            motivo="Cancelamento por teste automatizado.",
        )

        doc.refresh_from_db()
        assert doc.status == "cancelada"
        assert doc.protocolo.startswith("CANCEL-")
        assert "Cancelamento homologado" in (doc.mensagem_sefaz or "")

        assert result.status == "cancelada"
        assert result.chave_acesso == doc.chave_acesso
        assert result.protocolo == doc.protocolo


@pytest.mark.django_db(transaction=True)
def test_cancelar_nfce_idempotente_quando_ja_cancelada():
    """
    Quando o documento já está cancelado, a chamada é idempotente:
    não muda o estado, apenas retorna os dados atuais.
    """

    _bootstrap_public_tenant_and_domain()
    User = get_user_model()

    with schema_context(TENANT_SCHEMA):
        user = User.objects.create_user(username="oper-canc2", password="123456")

        filial = Filial.objects.create(
            cnpj="22222222000122",
            nome_fantasia="Filial Canc 3",
            uf="SP",
            csc_id="ID",
            csc_token="TK",
            ambiente="homolog",
        )

        _ensure_a1_valid(filial)

        term = Terminal.objects.create(
            identificador="T-CANC-02",
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
            chave_acesso="NFe" + "2" * 44,
            protocolo="CANCEL-XYZ",
            status="cancelada",
            mensagem_sefaz="Cancelamento homologado.",
        )

        result = cancelar_nfce(
            user=user,
            chave_acesso=doc.chave_acesso,
            filial_id=None,
            numero=None,
            serie=None,
            motivo="Chamando novamente o cancelamento.",
        )

        doc.refresh_from_db()
        assert doc.status == "cancelada"
        assert doc.protocolo == "CANCEL-XYZ"
        assert result.status == "cancelada"
        assert result.protocolo == "CANCEL-XYZ"
