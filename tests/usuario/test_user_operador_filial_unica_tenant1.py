# usuario/tests/test_user_operador_filial_unica_tenant1.py

import logging

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django_tenants.utils import schema_context

logger = logging.getLogger(__name__)


@pytest.mark.django_db(transaction=True)
def test_usuario_operador_vinculado_apenas_a_filial1_do_tenant1(two_tenants_with_admins):
    """
    Cenário base:

    - Tenant 1 e Tenant 2 provisionados via two_tenants_with_admins.
    - Tenant 1 já possui 1 Filial inicial (filial1).
    - Criamos um usuário OPERADOR vinculado APENAS à filial1.

    Validamos:

    - Ele acessa filial1 do tenant1 (UserFilial existe).
    - NÃO possui vínculo com nenhuma outra filial no tenant1.
    - NÃO existe nem aparece no tenant2.
    """
    schema1 = two_tenants_with_admins["schema1"]
    schema2 = two_tenants_with_admins["schema2"]

    logger.info(
        "Iniciando teste: usuário OPERADOR vinculado apenas à filial1 do tenant1."
    )

    User = get_user_model()
    user_app_label = User._meta.app_label
    UserFilial = apps.get_model(user_app_label, "UserFilial")
    FilialModel = apps.get_model("filial", "Filial")

    operador_username = "operador_t1_filial1"

    # ---------------------------
    # Tenant1: criação do usuário e vínculo com filial1
    # ---------------------------
    with schema_context(schema1):
        logger.info("Contexto: tenant1 (schema=%s).", schema1)

        assert FilialModel.objects.count() == 1, (
            "Pré-condição: tenant1 deve iniciar com 1 filial (a inicial)."
        )
        filial1 = FilialModel.objects.first()

        logger.info("Criando usuário OPERADOR em tenant1, vinculado à filial1.")
        operador = User.objects.create(
            username=operador_username,
            email="operador_filial1_t1@example.com",
            perfil="OPERADOR",
            is_superuser=False,
            is_staff=False,
            is_active=True,
        )
        operador.set_unusable_password()
        operador.save(update_fields=["password"])

        UserFilial.objects.create(
            user=operador,
            filial_id=filial1.id,
        )

        # Deve existir exatamente 1 vínculo de UserFilial para esse usuário
        vinculos = list(
            UserFilial.objects.filter(user=operador).values_list("filial_id", flat=True)
        )
        assert vinculos == [filial1.id], (
            "Usuário OPERADOR do tenant1 deve estar vinculado APENAS à filial1. "
            f"Vínculos encontrados: {vinculos}"
        )
        logger.info(
            "Usuário OPERADOR '%s' vinculado apenas à filial1 (id=%s) no tenant1.",
            operador_username,
            filial1.id,
        )

    # ---------------------------
    # Tenant2: ele não pode existir
    # ---------------------------
    with schema_context(schema2):
        logger.info(
            "Verificando se usuário OPERADOR '%s' aparece no tenant2 (não pode).",
            operador_username,
        )
        exists_in_tenant2 = User.objects.filter(username=operador_username).exists()
        assert not exists_in_tenant2, (
            "Usuário OPERADOR criado no tenant1 NÃO pode existir no tenant2."
        )
        logger.info(
            "Confirmação: usuário OPERADOR '%s' não existe no tenant2.",
            operador_username,
        )
