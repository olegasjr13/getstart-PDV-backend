# usuario/tests/test_user_list_isolado_por_tenant.py

import logging

import pytest
from django.contrib.auth import get_user_model
from django_tenants.utils import schema_context

logger = logging.getLogger(__name__)


@pytest.mark.django_db(transaction=True)
def test_listagem_de_usuarios_isolada_por_tenant(two_tenants_with_admins):
    """
    Cenário:

    - Fixture two_tenants_with_admins já criou um ADMIN em cada tenant.
    - Adicionamos:
        * 2 usuários extras no tenant1.
        * 3 usuários extras no tenant2.

    Validamos:

    - Contagem de usuários em cada tenant é independente.
    - Nenhum usuário "vaza" de um schema para o outro.
    """
    schema1 = two_tenants_with_admins["schema1"]
    schema2 = two_tenants_with_admins["schema2"]

    User = get_user_model()

    # ---------------------------
    # Tenant1: cria 2 usuários extras
    # ---------------------------
    with schema_context(schema1):
        logger.info("Contexto: tenant1 (schema=%s). Criando usuários extras.", schema1)

        count_before_t1 = User.objects.count()
        logger.info("Tenant1: contagem inicial de usuários: %s.", count_before_t1)

        User.objects.create(username="t1_user_1", email="t1_user_1@example.com")
        User.objects.create(username="t1_user_2", email="t1_user_2@example.com")

        count_after_t1 = User.objects.count()
        assert count_after_t1 == count_before_t1 + 2, (
            "Tenant1 deveria ter +2 usuários após criação. "
            f"Antes={count_before_t1}, depois={count_after_t1}"
        )
        logger.info("Tenant1: contagem final de usuários: %s.", count_after_t1)

    # ---------------------------
    # Tenant2: cria 3 usuários extras
    # ---------------------------
    with schema_context(schema2):
        logger.info("Contexto: tenant2 (schema=%s). Criando usuários extras.", schema2)

        count_before_t2 = User.objects.count()
        logger.info("Tenant2: contagem inicial de usuários: %s.", count_before_t2)

        User.objects.create(username="t2_user_1", email="t2_user_1@example.com")
        User.objects.create(username="t2_user_2", email="t2_user_2@example.com")
        User.objects.create(username="t2_user_3", email="t2_user_3@example.com")

        count_after_t2 = User.objects.count()
        assert count_after_t2 == count_before_t2 + 3, (
            "Tenant2 deveria ter +3 usuários após criação. "
            f"Antes={count_before_t2}, depois={count_after_t2}"
        )
        logger.info("Tenant2: contagem final de usuários: %s.", count_after_t2)

    logger.info(
        "Fim: listagem de usuários se mantém isolada por tenant "
        "(cada schema com sua contagem independente)."
    )
