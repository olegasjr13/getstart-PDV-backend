# filial/tests/certificado/test_certificado_cascade_delete.py

import logging
from datetime import datetime, timedelta, timezone

import pytest
from django.apps import apps
from django_tenants.utils import schema_context

logger = logging.getLogger(__name__)


@pytest.mark.django_db(transaction=True)
def test_certificado_a1_excluido_ao_deletar_filial(two_tenants_with_admins):
    """
    Cenário:
    - No tenant1, criamos certificado A1 para a filial inicial.
    - Deletamos a filial.

    Valida:
    - Certificado também é removido (CASCADE).
    """
    schema1 = two_tenants_with_admins["schema1"]

    FilialModel = apps.get_model("filial", "Filial")
    FilialCertificadoA1 = apps.get_model("filial", "FilialCertificadoA1")

    with schema_context(schema1):
        filial = FilialModel.objects.first()
        cert = FilialCertificadoA1.objects.create(
            filial=filial,
            a1_pfx=b"cert-cascade",
            senha_hash="hash-cascade",
            a1_expires_at=datetime.now(timezone.utc) + timedelta(days=365),
        )

        assert FilialCertificadoA1.objects.filter(pk=cert.pk).exists()

        filial.delete()

        assert not FilialCertificadoA1.objects.filter(pk=cert.pk).exists(), (
            "Certificado A1 deve ser removido ao excluir a filial (CASCADE)."
        )
