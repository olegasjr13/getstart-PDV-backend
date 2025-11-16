import uuid

import pytest
from django.contrib.auth import get_user_model
from django_tenants.utils import schema_context

from filial.models.filial_models import Filial
from fiscal.tests.test_nfce_atomicidade_rollback import TENANT_SCHEMA, _bootstrap_public_tenant_and_domain
from fiscal.tests.test_nfce_auditoria_logs import _ensure_a1_valid
from terminal.models.terminal_models import Terminal
from fiscal.models import NfceDocumento, NfceInutilizacao
from fiscal.services.inutilizacao_service import inutilizar_faixa_nfce



@pytest.mark.django_db(transaction=True)
def test_inutilizar_faixa_happy_path():
    """
    Inutiliza uma faixa sem documentos emitidos.
    """

    _bootstrap_public_tenant_and_domain()
    User = get_user_model()

    with schema_context(TENANT_SCHEMA):
        user = User.objects.create_user(username="oper-inut", password="123456")

        filial = Filial.objects.create(
            cnpj="33333333000133",
            nome_fantasia="Filial Inut",
            uf="SP",
            csc_id="ID",
            csc_token="TK",
            ambiente="homolog",
        )
        _ensure_a1_valid(filial)

        term = Terminal.objects.create(
            identificador="T-INUT-01",
            filial_id=filial.id,
            serie=1,
            numero_atual=1,
            ativo=True,
        )

        user.userfilial_set.create(filial_id=filial.id)

        req_id = uuid.uuid4()

        result = inutilizar_faixa_nfce(
            user=user,
            filial_id=str(filial.id),
            serie=term.serie,
            numero_inicial=10,
            numero_final=20,
            motivo="Faixa não utilizada por erro de configuração.",
            request_id=req_id,
        )

        assert result.status == "inutilizada"
        assert result.numero_inicial == 10
        assert result.numero_final == 20
        assert result.filial_id == str(filial.id)

        inutil = NfceInutilizacao.objects.get(request_id=req_id)
        assert inutil.status == "inutilizada"
        assert inutil.numero_inicial == 10
        assert inutil.numero_final == 20


@pytest.mark.django_db(transaction=True)
def test_inutilizar_faixa_com_numero_emitido_dispara_erro():
    """
    Não permite inutilizar faixa que contém números já emitidos.
    """

    from rest_framework.exceptions import APIException

    _bootstrap_public_tenant_and_domain()
    User = get_user_model()

    with schema_context(TENANT_SCHEMA):
        user = User.objects.create_user(username="oper-inut2", password="123456")

        filial = Filial.objects.create(
            cnpj="44444444000144",
            nome_fantasia="Filial Inut 2",
            uf="SP",
            csc_id="ID",
            csc_token="TK",
            ambiente="homolog",
        )
        _ensure_a1_valid(filial)

        term = Terminal.objects.create(
            identificador="T-INUT-02",
            filial_id=filial.id,
            serie=1,
            numero_atual=1,
            ativo=True,
        )

        user.userfilial_set.create(filial_id=filial.id)

        # Documento emitido no meio da faixa
        NfceDocumento.objects.create(
            request_id=uuid.uuid4(),
            filial=filial,
            terminal=term,
            numero=15,
            serie=term.serie,
            chave_acesso="NFe" + "9" * 44,
            protocolo="PROTO-EMIT",
            status="autorizada",
            mensagem_sefaz="Autorizado uso NFC-e.",
        )

        with pytest.raises(APIException) as excinfo:
            inutilizar_faixa_nfce(
                user=user,
                filial_id=str(filial.id),
                serie=term.serie,
                numero_inicial=10,
                numero_final=20,
                motivo="Tentativa de inutilizar faixa com doc emitido.",
                request_id=uuid.uuid4(),
            )

        detail = excinfo.value.detail
        assert isinstance(detail, dict)
        assert detail.get("code") == "FISCAL_4101"
