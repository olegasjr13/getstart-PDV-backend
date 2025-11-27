# usuario/tests/test_user_delete_isolado_por_tenant.py

import logging

import pytest
from django.contrib.auth import get_user_model
from django_tenants.utils import schema_context

logger = logging.getLogger(__name__)


@pytest.mark.django_db(transaction=True)
def test_exclusao_de_usuario_no_tenant1_nao_afeta_tenant2(two_tenants_with_admins):
    """
    Cenário:

    - Tenant1 e Tenant2 provisionados.
    - Criamos em CADA tenant um usuário com o MESMO username.

    Ex:
      - tenant1: username='usuario_compartilhado'
      - tenant2: username='usuario_compartilhado'

    Validamos:

    - Ao deletar o usuário no tenant1:
        * Ele some apenas do schema do tenant1.
        * Ele CONTINUA existindo no schema do tenant2.
    """
    schema1 = two_tenants_with_admins["schema1"]
    schema2 = two_tenants_with_admins["schema2"]

    logger.info(
        "Iniciando teste: exclusão de usuário no tenant1 não afeta usuário no tenant2."
    )

    User = get_user_model()
    username_compartilhado = "usuario_compartilhado"

    # ---------------------------
    # Cria usuário em tenant1
    # ---------------------------
    with schema_context(schema1):
        logger.info("Criando usuário '%s' no tenant1 (schema=%s).",
                    username_compartilhado, schema1)
        user_t1 = User.objects.create(
            username=username_compartilhado,
            email="compartilhado_t1@example.com",
            is_active=True,
        )
        assert User.objects.filter(
            username=username_compartilhado
        ).exists(), "Usuário deve existir no tenant1 após criação."

    # ---------------------------
    # Cria usuário em tenant2
    # ---------------------------
    with schema_context(schema2):
        logger.info("Criando usuário '%s' no tenant2 (schema=%s).",
                    username_compartilhado, schema2)
        user_t2 = User.objects.create(
            username=username_compartilhado,
            email="compartilhado_t2@example.com",
            is_active=True,
        )
        assert User.objects.filter(
            username=username_compartilhado
        ).exists(), "Usuário deve existir no tenant2 após criação."

    # ---------------------------
    # Deleta usuário no tenant1
    # ---------------------------
    with schema_context(schema1):
        logger.info("Deletando usuário '%s' no tenant1.", username_compartilhado)
        user_t1.delete()

        exists_t1 = User.objects.filter(username=username_compartilhado).exists()
        assert not exists_t1, (
            "Após deleção, usuário '%s' não deve mais existir no tenant1."
            % username_compartilhado
        )
        logger.info(
            "Usuário '%s' removido com sucesso do tenant1.", username_compartilhado
        )

    # ---------------------------
    # Verifica que continua existindo no tenant2
    # ---------------------------
    with schema_context(schema2):
        exists_t2 = User.objects.filter(username=username_compartilhado).exists()
        assert exists_t2, (
            "Usuário '%s' deve continuar existindo no tenant2 após deleção no tenant1."
            % username_compartilhado
        )
        logger.info(
            "Confirmação: usuário '%s' ainda existe no tenant2 após deleção no tenant1.",
            username_compartilhado,
        )
