# usuario/tests/test_users_multitenant.py

import logging

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django_tenants.utils import schema_context

logger = logging.getLogger(__name__)


@pytest.mark.django_db(transaction=True)
def test_usuario_operador_vinculado_apenas_a_filial_do_seu_tenant(two_tenants_with_admins):
    """
    Cenário:

    - Tenant 1 e Tenant 2 já provisionados via fixture two_tenants_with_admins.
    - No tenant 1:
        * Já existe uma filial inicial (filial1) criada no provisionamento.
        * Criamos uma segunda filial (filial2), reutilizando o ENDEREÇO da filial1.
        * Criamos um usuário OPERADOR vinculado APENAS à filial1.
    - No tenant 2:
        * Não criamos esse usuário.

    Verificamos:

    - Usuário operador:
        * acessa filial1 do tenant1 (existe vínculo UserFilial).
        * NÃO acessa filial2 do tenant1 (não há vínculo).
        * NÃO existe / NÃO possui vínculo em nenhuma filial do tenant2.
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

    operador_username = "operador_t1_f1"

    # ---------------------------
    # Dentro do tenant1: criar filiais e usuário operador
    # ---------------------------
    with schema_context(schema1):
        logger.info("Contexto: tenant1 (schema=%s).", schema1)

        # Já existe 1 filial criada no provisionamento (filial1)
        assert FilialModel.objects.count() == 1, (
            "Pré-condição: tenant1 deveria começar com 1 filial (a inicial)."
        )
        filial1 = FilialModel.objects.first()
        endereco_filial1 = filial1.endereco

        # Criar uma segunda filial no tenant1 REUTILIZANDO o mesmo endereço
        filial2 = FilialModel.objects.create(
            razao_social="Filial 2 Tenant 1",
            nome_fantasia="Loja 2 T1",
            cnpj="22222222000100",
            endereco=endereco_filial1,  # ✅ endereço válido, sem violar NOT NULL
            ativo=True,
        )
        logger.info(
            "Criadas filiais em tenant1: filial1_id=%s, filial2_id=%s (mesmo endereço).",
            filial1.id,
            filial2.id,
        )

        # Criar usuário OPERADOR vinculado apenas à filial1
        logger.info(
            "Criando usuário OPERADOR em tenant1, vinculado apenas à filial1."
        )
        operador = User.objects.create(
            username=operador_username,
            email="operador_t1@example.com",
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

        # --- Validações no tenant1 ---

        # Acessa filial1 (OK)
        logger.info(
            "Iniciando: operador do tenant1 acessando filial1 do tenant1."
        )
        assert UserFilial.objects.filter(
            user=operador, filial_id=filial1.id
        ).exists(), (
            "Usuário OPERADOR deveria estar vinculado à filial1 do tenant1."
        )
        logger.info(
            "Fim: operador do tenant1 acessando filial1 do tenant1 -> PERMITIDO."
        )

        # Não acessa filial2 (não há vínculo)
        logger.info(
            "Iniciando: operador do tenant1 tentando acessar filial2 do tenant1."
        )
        assert not UserFilial.objects.filter(
            user=operador, filial_id=filial2.id
        ).exists(), (
            "Usuário OPERADOR NÃO deveria estar vinculado à filial2 do tenant1."
        )
        logger.info(
            "Fim: operador do tenant1 tentando acessar filial2 do tenant1 -> "
            "NÃO PERMITIDO (sem vínculo)."
        )

    # ---------------------------
    # Dentro do tenant2: garantir que esse usuário não existe / não tem vínculo
    # ---------------------------
    with schema_context(schema2):
        logger.info(
            "Contexto: tenant2 (schema=%s). Verificando se operador do tenant1 "
            "aparece aqui (não pode).",
            schema2,
        )

        existe_user_operador_no_tenant2 = User.objects.filter(
            username=operador_username
        ).exists()
        assert not existe_user_operador_no_tenant2, (
            "Usuário OPERADOR criado no tenant1 NÃO pode existir no tenant2 "
            "(isolamento de tenants)."
        )

        logger.info(
            "Confirmação: usuário OPERADOR '%s' não existe no tenant2.",
            operador_username,
        )
