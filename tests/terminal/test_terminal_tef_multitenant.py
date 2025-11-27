# terminal/tests/test_terminal_tef_multitenant.py

import logging

import pytest
from django.apps import apps
from django_tenants.utils import schema_context

logger = logging.getLogger(__name__)


@pytest.mark.django_db(transaction=True)
def test_criar_terminal_com_campos_tef_em_um_tenant(two_tenants_with_admins):
    """
    Cenário:
    - No tenant1, criar um terminal com permite_tef=True e tef_terminal_id preenchido.

    Esperado:
    - Terminal é criado com os campos TEF corretos.
    """
    schema1 = two_tenants_with_admins["schema1"]
    FilialModel = apps.get_model("filial", "Filial")
    TerminalModel = apps.get_model("terminal", "Terminal")

    with schema_context(schema1):
        filial = FilialModel.objects.first()

        terminal = TerminalModel.objects.create(
            filial=filial,
            identificador="CX_TEFA",
            ativo=True,
            permite_tef=True,
            tef_terminal_id="PDV001",
        )

        assert terminal.permite_tef is True
        assert terminal.tef_terminal_id == "PDV001"


@pytest.mark.django_db(transaction=True)
def test_terminal_tef_isolamento_entre_tenants(two_tenants_with_admins):
    """
    Cenário:
    - Criar terminais com configurações TEF diferentes em tenant1 e tenant2.

    Esperado:
    - Alterações em um tenant não afetam o outro.
    """
    schema1 = two_tenants_with_admins["schema1"]
    schema2 = two_tenants_with_admins["schema2"]

    FilialModel = apps.get_model("filial", "Filial")
    TerminalModel = apps.get_model("terminal", "Terminal")

    with schema_context(schema1):
        filial_t1 = FilialModel.objects.first()
        t1 = TerminalModel.objects.create(
            filial=filial_t1,
            identificador="CX01",
            ativo=True,
            permite_tef=True,
            tef_terminal_id="PDV_T1",
        )

    with schema_context(schema2):
        filial_t2 = FilialModel.objects.first()
        t2 = TerminalModel.objects.create(
            filial=filial_t2,
            identificador="CX01",
            ativo=True,
            permite_tef=False,
            tef_terminal_id=None,
        )

    # Edita apenas tenant1
    with schema_context(schema1):
        t1.permite_tef = False
        t1.tef_terminal_id = "PDV_T1_EDIT"
        t1.save(update_fields=["permite_tef", "tef_terminal_id"])

        t1_ref = TerminalModel.objects.get(pk=t1.pk)
        assert t1_ref.permite_tef is False
        assert t1_ref.tef_terminal_id == "PDV_T1_EDIT"

    # Verifica tenant2 intacto
    with schema_context(schema2):
        t2_ref = TerminalModel.objects.get(pk=t2.pk)
        assert t2_ref.permite_tef is False
        assert t2_ref.tef_terminal_id is None
