# usuario/tests/test_user_operador_multiplas_filiais_mesmo_tenant.py

import logging

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django_tenants.utils import schema_context

logger = logging.getLogger(__name__)


@pytest.mark.django_db(transaction=True)
def test_usuario_operador_vinculado_apenas_as_filiais1_e2_do_tenant1(two_tenants_with_admins):
    """
    Cenário:

    - Tenant 1 provisionado com 1 filial inicial (filial1).
    - Criamos:
        * filial2 e filial3 no tenant1 (reutilizando o ENDEREÇO de filial1).
        * usuário OPERADOR vinculado APENAS às filiais 1 e 2.

    Validamos:

    - Há vínculos de UserFilial SOMENTE com filial1 e filial2.
    - NÃO há vínculo com filial3.
    """
    schema1 = two_tenants_with_admins["schema1"]

    logger.info(
        "Iniciando teste: usuário OPERADOR vinculado apenas às filiais1 e 2 no tenant1."
    )

    User = get_user_model()
    user_app_label = User._meta.app_label
    UserFilial = apps.get_model(user_app_label, "UserFilial")
    FilialModel = apps.get_model("filial", "Filial")

    operador_username = "operador_t1_filiais12"

    with schema_context(schema1):
        logger.info("Contexto: tenant1 (schema=%s).", schema1)

        assert FilialModel.objects.count() == 1, (
            "Pré-condição: tenant1 deve iniciar com 1 filial (a inicial)."
        )
        filial1 = FilialModel.objects.first()
        endereco = filial1.endereco

        # Criar filial2 e filial3 com o mesmo endereço
        filial2 = FilialModel.objects.create(
            razao_social="Filial 2 Tenant 1",
            nome_fantasia="Loja 2 T1",
            cnpj="44444444000100",
            endereco=endereco,
            ativo=True,
        )
        filial3 = FilialModel.objects.create(
            razao_social="Filial 3 Tenant 1",
            nome_fantasia="Loja 3 T1",
            cnpj="55555555000100",
            endereco=endereco,
            ativo=True,
        )

        logger.info(
            "Criadas filiais em tenant1: filial1_id=%s, filial2_id=%s, filial3_id=%s.",
            filial1.id,
            filial2.id,
            filial3.id,
        )

        # Criar usuário OPERADOR
        operador = User.objects.create(
            username=operador_username,
            email="operador_filiais12_t1@example.com",
            perfil="OPERADOR",
            is_superuser=False,
            is_staff=False,
            is_active=True,
        )
        operador.set_unusable_password()
        operador.save(update_fields=["password"])

        # Vínculo apenas com filial1 e filial2
        UserFilial.objects.bulk_create(
            [
                UserFilial(user=operador, filial_id=filial1.id),
                UserFilial(user=operador, filial_id=filial2.id),
            ]
        )

        # Lista de filiais vinculadas a esse usuário
        vinculos = set(
            UserFilial.objects.filter(user=operador).values_list("filial_id", flat=True)
        )
        expected = {filial1.id, filial2.id}
        assert vinculos == expected, (
            "Usuário OPERADOR deve estar vinculado apenas às filiais1 e 2. "
            f"Esperado: {expected}, encontrado: {vinculos}"
        )

        # Garante explicitamente que NÃO há vínculo com filial3
        assert not UserFilial.objects.filter(
            user=operador, filial_id=filial3.id
        ).exists(), (
            "Usuário OPERADOR NÃO deveria estar vinculado à filial3 do tenant1."
        )

        logger.info(
            "Fim: usuário OPERADOR '%s' vinculado apenas às filiais1 (%s) e 2 (%s) "
            "no tenant1. Sem vínculo com filial3 (%s).",
            operador_username,
            filial1.id,
            filial2.id,
            filial3.id,
        )
