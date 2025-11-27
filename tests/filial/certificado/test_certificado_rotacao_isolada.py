# filial/tests/certificado/test_certificado_rotacao_isolada.py

import logging
from datetime import datetime, timedelta, timezone

import pytest
from django.apps import apps
from django_tenants.utils import schema_context

logger = logging.getLogger(__name__)


@pytest.mark.django_db(transaction=True)
def test_rotacao_certificado_a1_no_tenant1_nao_afeta_tenant2(two_tenants_with_admins):
    """
    Cenário:
    - Criamos certificado A1 para a filial inicial em AMBOS os tenants.
    - No tenant1, simulamos rotação (atualização dos dados do certificado).

    Valida:
    - Certificado do tenant1 é atualizado corretamente.
    - Certificado do tenant2 permanece exatamente com os valores originais.
    """
    schema1 = two_tenants_with_admins["schema1"]
    schema2 = two_tenants_with_admins["schema2"]

    FilialModel = apps.get_model("filial", "Filial")
    FilialCertificadoA1 = apps.get_model("filial", "FilialCertificadoA1")

    # ----------------------------------------------------------------------
    # Criar certificados iniciais em ambos tenants
    # ----------------------------------------------------------------------
    with schema_context(schema1):
        filial1 = FilialModel.objects.first()
        cert1 = FilialCertificadoA1.objects.create(
            filial=filial1,
            a1_pfx=b"cert-t1-v1",
            senha_hash="hash-v1-t1",
            a1_expires_at=datetime.now(timezone.utc) + timedelta(days=365),
            numero_serie="SERIE_T1_V1",
            emissor="AC T1 V1",
        )

    with schema_context(schema2):
        filial2 = FilialModel.objects.first()
        cert2 = FilialCertificadoA1.objects.create(
            filial=filial2,
            a1_pfx=b"cert-t2-v1",
            senha_hash="hash-v1-t2",
            a1_expires_at=datetime.now(timezone.utc) + timedelta(days=365),
            numero_serie="SERIE_T2_V1",
            emissor="AC T2 V1",
        )

    # ----------------------------------------------------------------------
    # Rotação de certificado no tenant1
    # ----------------------------------------------------------------------
    with schema_context(schema1):
        logger.info("Rotacionando certificado A1 no tenant1 (schema=%s).", schema1)
        cert1_db = FilialCertificadoA1.objects.get(pk=cert1.pk)

        cert1_db.a1_pfx = b"cert-t1-v2"
        cert1_db.senha_hash = "hash-v2-t1"
        cert1_db.numero_serie = "SERIE_T1_V2"
        cert1_db.emissor = "AC T1 V2"
        cert1_db.save(
            update_fields=["a1_pfx", "senha_hash", "numero_serie", "emissor"]
        )

        # Recarrega e valida que foi atualizado corretamente
        cert1_refresh = FilialCertificadoA1.objects.get(pk=cert1.pk)

        # a1_pfx é BinaryField -> volta como memoryview -> converter pra bytes antes de comparar
        assert bytes(cert1_refresh.a1_pfx) == b"cert-t1-v2"
        assert cert1_refresh.senha_hash == "hash-v2-t1"
        assert cert1_refresh.numero_serie == "SERIE_T1_V2"
        assert cert1_refresh.emissor == "AC T1 V2"

        logger.info(
            "Certificado do tenant1 rotacionado com sucesso: serie=%s, emissor=%s",
            cert1_refresh.numero_serie,
            cert1_refresh.emissor,
        )

    # ----------------------------------------------------------------------
    # Verificar que o certificado do tenant2 permaneceu intacto
    # ----------------------------------------------------------------------
    with schema_context(schema2):
        logger.info(
            "Verificando se rotação no tenant1 afetou certificado no tenant2 (schema=%s).",
            schema2,
        )

        cert2_refresh = FilialCertificadoA1.objects.get(pk=cert2.pk)

        # Converter BinaryField para bytes na comparação
        assert bytes(cert2_refresh.a1_pfx) == b"cert-t2-v1"
        assert cert2_refresh.senha_hash == "hash-v1-t2"
        assert cert2_refresh.numero_serie == "SERIE_T2_V1"
        assert cert2_refresh.emissor == "AC T2 V1", (
            "Rotação de certificado em tenant1 NÃO pode alterar dados do tenant2."
        )

        logger.info(
            "Confirmação: certificado do tenant2 permaneceu intacto após rotação no tenant1."
        )
