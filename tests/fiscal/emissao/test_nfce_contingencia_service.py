# fiscal/tests/emissao/test_nfce_contingencia_service.py

import uuid
from datetime import timedelta

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.test.utils import override_settings
from django.utils import timezone
from django_tenants.utils import get_tenant_model, schema_context

from filial.models.filial_models import Filial
from terminal.models.terminal_models import Terminal
from fiscal.models import (
    NfcePreEmissao,
    NfceDocumento,
    NfceAuditoria,
)
from fiscal.sefaz_clients import MockSefazClientAlwaysFail
from fiscal.services.emissao_service import emitir_nfce, EmitirNfceResult

TENANT_SCHEMA = "12345678000199"
TENANT_HOST = "cliente-demo.localhost"


def _bootstrap_public_tenant_and_domain():
    Tenant = get_tenant_model()
    Domain = apps.get_model("tenants", "Domain")

    Tenant.objects.get_or_create(
        schema_name="public",
        defaults=dict(
            cnpj_raiz="00000000000000",
            nome="PUBLIC",
            premium_db_alias=None,
        ),
    )

    ten, _ = Tenant.objects.get_or_create(
        schema_name=TENANT_SCHEMA,
        defaults=dict(
            cnpj_raiz=TENANT_SCHEMA,
            nome="Tenant Teste",
            premium_db_alias=None,
        ),
    )

    dom, created_dom = Domain.objects.get_or_create(
        domain=TENANT_HOST,
        defaults=dict(tenant=ten, is_primary=True),
    )
    if not created_dom and dom.tenant_id != ten.id:
        dom.tenant = ten
        dom.is_primary = True
        dom.save(update_fields=["tenant", "is_primary"])


def _ensure_a1_valid(filial: Filial):
    filial.a1_expires_at = timezone.now() + timedelta(days=1)
    filial.save(update_fields=["a1_expires_at"])


@override_settings(
    ROOT_URLCONF="config.urls",
    ALLOWED_HOSTS=["*", TENANT_HOST, "testserver"],
)
@pytest.mark.django_db(transaction=True)
def test_emitir_nfce_em_contingencia_quando_sefaz_falha_tecnicamente():
    """
    Quando a SEFAZ falha tecnicamente (SefazTechnicalError):

      - Um NfceDocumento é criado com status 'contingencia_pendente'
        e em_contingencia=True.
      - Um registro em NfceAuditoria é criado com tipo_evento
        'EMISSAO_CONTINGENCIA_ATIVADA'.
      - O DTO EmitirNfceResult reflete este estado.
    """

    _bootstrap_public_tenant_and_domain()
    User = get_user_model()

    with schema_context(TENANT_SCHEMA):
        user = User.objects.create_user(username="oper-cont", password="123456")

        filial = Filial.objects.create(
            cnpj="99999999000199",
            nome_fantasia="Filial Contingência",
            uf="SP",
            csc_id="ID",
            csc_token="TK",
            ambiente="homolog",
        )
        _ensure_a1_valid(filial)

        term = Terminal.objects.create(
            identificador="T-CONT-01",
            filial_id=filial.id,
            serie=1,
            numero_atual=1,
            ativo=True,
        )

        user.userfilial_set.create(filial_id=filial.id)

        req_id = uuid.uuid4()

        pre = NfcePreEmissao.objects.create(
            filial_id=filial.id,
            terminal_id=term.id,
            numero=1,
            serie=1,
            request_id=req_id,
            payload={
                "itens": [],
                "pagamentos": [],
                "cliente": None,
            },
        )

        # Client SEFAZ que sempre falha tecnicamente
        sefaz_client = MockSefazClientAlwaysFail(ambiente="homolog", uf="SP")

        result = emitir_nfce(
            user=user,
            request_id=req_id,
            sefaz_client=sefaz_client,
        )

        # Verificações sobre o DTO
        assert isinstance(result, EmitirNfceResult)
        assert result.status == "contingencia_pendente"
        assert result.em_contingencia is True
        assert result.numero == pre.numero
        assert result.serie == pre.serie
        assert result.filial_id == str(filial.id)
        assert result.terminal_id == str(term.id)
        # Em contingência não temos chave/protocolo/xml
        assert result.chave_acesso is None
        assert result.protocolo is None
        assert result.xml_autorizado is None

        # Documento em contingência
        docs = NfceDocumento.objects.filter(request_id=req_id)
        assert docs.count() == 1
        doc = docs.first()

        assert doc.status == "contingencia_pendente"
        assert doc.em_contingencia is True
        assert doc.contingencia_ativada_em is not None
        assert "Falha técnica simulada" in (doc.mensagem_sefaz or "")

        # Auditoria de contingência
        audits = NfceAuditoria.objects.filter(
            request_id=req_id,
            tipo_evento="EMISSAO_CONTINGENCIA_ATIVADA",
        )
        assert audits.count() == 1
        audit = audits.first()

        assert audit.nfce_documento_id == doc.id
        assert audit.filial_id == filial.id
        assert audit.terminal_id == term.id
        assert audit.user_id == user.id
        assert audit.codigo_retorno in ("TECH_FAIL", None)  # depende do mock
        assert "Falha técnica simulada" in (audit.mensagem_retorno or "")
        assert audit.ambiente == filial.ambiente
        assert audit.uf == filial.uf
