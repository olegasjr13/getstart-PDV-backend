# filial/tests/certificado/test_certificado_isolamento_tenants.py

import logging
from datetime import datetime, timedelta, timezone

import pytest
from django.apps import apps
from django_tenants.utils import schema_context

logger = logging.getLogger(__name__)


@pytest.mark.django_db(transaction=True)
def test_certificado_a1_criado_no_tenant1_nao_existe_no_tenant2(two_tenants_with_admins):
    """
    Cenário:
    - Criamos um FilialCertificadoA1 apenas para a filial inicial do tenant1.

    Valida:
    - Tenant1 possui 1 certificado.
    - Tenant2 não possui nenhum.
    """
    schema1 = two_tenants_with_admins["schema1"]
    schema2 = two_tenants_with_admins["schema2"]

    FilialModel = apps.get_model("filial", "Filial")
    FilialCertificadoA1 = apps.get_model("filial", "FilialCertificadoA1")

    with schema_context(schema1):
        filial = FilialModel.objects.first()
        assert filial is not None

        FilialCertificadoA1.objects.create(
            filial=filial,
            a1_pfx=b"fake-binary-data",
            senha_hash="hash-senha",
            a1_expires_at=datetime.now(timezone.utc) + timedelta(days=365),
            numero_serie="123456",
            emissor="Autoridade Certificadora T1",
        )
        assert FilialCertificadoA1.objects.count() == 1

    with schema_context(schema2):
        assert FilialCertificadoA1.objects.count() == 0, (
            "Certificado criado no tenant1 não pode aparecer no tenant2."
        )
