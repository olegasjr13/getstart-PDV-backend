# usuario/tests/test_user_filial_unicidade.py

import logging

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django_tenants.utils import schema_context

logger = logging.getLogger(__name__)


@pytest.mark.django_db(transaction=True)
def test_userfilial_nao_permite_vinculo_duplicado(two_tenants_with_admins):
    """
    Garante que a constraint unique_together (user, filial_id)
    está efetivamente ativa e protegendo contra duplicidades.

    Cenário:

    - No tenant1:
        * Criamos usuário OPERADOR.
        * Vinculamos à filial1 (UserFilial).
        * Tentamos criar OUTRO registro UserFilial com o MESMO (user, filial_id).

    Esperado:
    - IntegrityError (ou equivalente) disparado pelo banco.
    """
    schema1 = two_tenants_with_admins["schema1"]

    User = get_user_model()
    user_app_label = User._meta.app_label
    UserFilial = apps.get_model(user_app_label, "UserFilial")
    FilialModel = apps.get_model("filial", "Filial")

    operador_username = "operador_vinculo_unico"

    with schema_context(schema1):
        logger.info(
            "Iniciando teste de unicidade UserFilial no tenant1 (schema=%s).",
            schema1,
        )

        filial1 = FilialModel.objects.first()
        assert filial1 is not None, "Pré-condição: deve existir uma filial inicial."

        operador = User.objects.create(
            username=operador_username,
            email="vinculo_unico_t1@example.com",
            perfil="OPERADOR",
            is_active=True,
        )

        # Primeiro vínculo OK
        UserFilial.objects.create(
            user=operador,
            filial_id=filial1.id,
        )

        # Segundo vínculo duplicado -> deve falhar
        with pytest.raises(IntegrityError):
            UserFilial.objects.create(
                user=operador,
                filial_id=filial1.id,
            )

        logger.info(
            "Fim: constraint de unicidade (user, filial_id) em UserFilial validada "
            "com sucesso (duplicidade gerou IntegrityError)."
        )
