# filial/tests/test_filial_multitenant.py

import logging

import pytest
from django.apps import apps
from django.db import IntegrityError
from django_tenants.utils import schema_context

logger = logging.getLogger(__name__)


@pytest.mark.django_db(transaction=True)
def test_admin_tenant1_cria_filial_somente_no_tenant1(two_tenants_with_admins):
    """
    Cenário:

    - Tenant 1 e Tenant 2 já provisionados via fixture two_tenants_with_admins.
      => Cada um já tem UMA filial inicial, com endereço válido.

    - No tenant 1:
        * Criamos uma nova Filial reutilizando o mesmo endereço da filial inicial.

    Verificamos:

    - A nova filial existe apenas no schema do tenant 1.
    - No tenant 2 NÃO existe nenhuma filial com o CNPJ da nova filial.
    """
    schema1 = two_tenants_with_admins["schema1"]
    schema2 = two_tenants_with_admins["schema2"]

    logger.info(
        "Iniciando teste: admin do tenant1 criando nova filial no tenant1, "
        "e garantindo que não aparece no tenant2."
    )

    FilialModel = apps.get_model("filial", "Filial")

    # ---------------------------
    # Admin tenant1 cria nova filial no tenant1
    # ---------------------------
    with schema_context(schema1):
        logger.info("Criando nova filial no tenant1 (schema=%s).", schema1)

        # Já existe uma filial criada pelo provisionamento -> usamos o mesmo endereço
        assert FilialModel.objects.count() == 1, (
            "Antes do teste, o tenant1 deveria ter exatamente 1 filial (a inicial)."
        )
        filial_inicial = FilialModel.objects.first()
        endereco_inicial = filial_inicial.endereco

        nova_filial_cnpj = "11111111000100"

        nova_filial = FilialModel.objects.create(
            razao_social="Filial Extra Tenant 1",
            nome_fantasia="Loja Extra T1",
            cnpj=nova_filial_cnpj,
            endereco=endereco_inicial,  # REUTILIZA endereço válido da filial inicial
            ativo=True,
        )

        logger.info(
            "Fim criação filial no tenant1. filial_id=%s, cnpj=%s",
            nova_filial.id,
            nova_filial.cnpj,
        )

        # Deve haver 2 filiais agora no tenant1 (a inicial + a nova)
        assert FilialModel.objects.count() == 2, (
            "Tenant1 deveria ter 2 filiais (inicial + nova)."
        )
        assert FilialModel.objects.filter(cnpj=nova_filial_cnpj).exists(), (
            "Nova filial com CNPJ %s deveria existir no tenant1." % nova_filial_cnpj
        )

    # ---------------------------
    # Verificar que essa filial NÃO existe no tenant2
    # ---------------------------
    with schema_context(schema2):
        logger.info(
            "Verificando se a filial criada no tenant1 'aparece' no tenant2 (schema=%s).",
            schema2,
        )

        existe_no_tenant2 = FilialModel.objects.filter(
            cnpj=nova_filial_cnpj
        ).exists()

        assert not existe_no_tenant2, (
            "Filial criada no tenant1 (CNPJ %s) NÃO pode existir no tenant2 "
            "(isolamento entre tenants violado)." % nova_filial_cnpj
        )

        logger.info(
            "Confirmação: filial de CNPJ %s não existe no tenant2.",
            nova_filial_cnpj,
        )


@pytest.mark.django_db(transaction=True)
def test_filial_nao_pode_ser_criada_sem_endereco(two_tenants_with_admins):
    """
    Garante que a modelagem da Filial exige endereço (NOT NULL no DB).

    Cenário:
    - No tenant1, tentar criar uma Filial com endereco=None.

    Esperado:
    - Levanta IntegrityError do banco de dados.
    """
    schema1 = two_tenants_with_admins["schema1"]
    FilialModel = apps.get_model("filial", "Filial")

    with schema_context(schema1):
        logger.info(
            "Iniciando: tentativa de criar filial SEM endereço no tenant1 (schema=%s).",
            schema1,
        )
        with pytest.raises(IntegrityError):
            FilialModel.objects.create(
                razao_social="Filial Sem Endereço",
                nome_fantasia="Loja Sem Endereço",
                cnpj="22222222000100",
                endereco=None,  # viola NOT NULL
                ativo=True,
            )
        logger.info(
            "Fim: criação de filial sem endereço corretamente bloqueada por IntegrityError."
        )


@pytest.mark.django_db(transaction=True)
def test_mesmo_cnpj_pode_ser_usado_em_tenants_diferentes(two_tenants_with_admins):
    """
    Garante que a restrição de CNPJ é por tenant (schema), não global.

    Cenário:
    - No tenant1: criar nova Filial com CNPJ X.
    - No tenant2: criar nova Filial com o MESMO CNPJ X.

    Esperado:
    - Ambas criações são permitidas (schemas isolados).
    """
    schema1 = two_tenants_with_admins["schema1"]
    schema2 = two_tenants_with_admins["schema2"]

    FilialModel = apps.get_model("filial", "Filial")
    cnpj_compartilhado = "33333333000100"

    # ---------------------------
    # Criar filial com CNPJ X no tenant1
    # ---------------------------
    with schema_context(schema1):
        logger.info(
            "Criando filial com CNPJ compartilhado no tenant1 (schema=%s).", schema1
        )

        filial_inicial_t1 = FilialModel.objects.first()
        endereco_t1 = filial_inicial_t1.endereco

        FilialModel.objects.create(
            razao_social="Filial CNPJ Compartilhado T1",
            nome_fantasia="Loja CNPJ T1",
            cnpj=cnpj_compartilhado,
            endereco=endereco_t1,
            ativo=True,
        )

        assert FilialModel.objects.filter(cnpj=cnpj_compartilhado).count() == 1, (
            "Tenant1 deveria ter exatamente 1 filial com CNPJ compartilhado."
        )

    # ---------------------------
    # Criar filial com CNPJ X no tenant2
    # ---------------------------
    with schema_context(schema2):
        logger.info(
            "Criando filial com CNPJ compartilhado no tenant2 (schema=%s).", schema2
        )

        filial_inicial_t2 = FilialModel.objects.first()
        endereco_t2 = filial_inicial_t2.endereco

        FilialModel.objects.create(
            razao_social="Filial CNPJ Compartilhado T2",
            nome_fantasia="Loja CNPJ T2",
            cnpj=cnpj_compartilhado,
            endereco=endereco_t2,
            ativo=True,
        )

        assert FilialModel.objects.filter(cnpj=cnpj_compartilhado).count() == 1, (
            "Tenant2 deveria ter exatamente 1 filial com CNPJ compartilhado."
        )

    logger.info(
        "Fim: mesmo CNPJ %s usado em tenants diferentes sem conflito (isolamento OK).",
        cnpj_compartilhado,
    )


@pytest.mark.django_db(transaction=True)
def test_exclusao_de_filial_no_tenant1_nao_afeta_tenant2(two_tenants_with_admins):
    """
    Cenário:

    - Cada tenant começa com 1 Filial (a inicial).
    - No tenant1, deletamos a Filial inicial.

    Verificamos:

    - No tenant1: Filial inicial foi removida.
    - No tenant2: Filial inicial continua existindo (isolamento por schema).
    """
    schema1 = two_tenants_with_admins["schema1"]
    schema2 = two_tenants_with_admins["schema2"]

    FilialModel = apps.get_model("filial", "Filial")

    # ---------------------------
    # Antes: cada tenant deve ter 1 filial
    # ---------------------------
    with schema_context(schema1):
        assert FilialModel.objects.count() == 1, (
            "Pré-condição: tenant1 deveria começar com 1 filial."
        )

    with schema_context(schema2):
        assert FilialModel.objects.count() == 1, (
            "Pré-condição: tenant2 deveria começar com 1 filial."
        )

    # ---------------------------
    # Deleta filial do tenant1
    # ---------------------------
    with schema_context(schema1):
        logger.info("Deletando filial inicial do tenant1 (schema=%s).", schema1)
        filial_t1 = FilialModel.objects.first()
        filial_t1.delete()

        assert FilialModel.objects.count() == 0, (
            "Após a exclusão, tenant1 não deveria ter mais filiais."
        )
        logger.info(
            "Filial inicial do tenant1 removida com sucesso; nenhum registro de Filial restante."
        )

    # ---------------------------
    # Verifica que tenant2 continua intacto
    # ---------------------------
    with schema_context(schema2):
        logger.info(
            "Verificando se exclusão de filial no tenant1 afetou tenant2 (schema=%s).",
            schema2,
        )

        assert FilialModel.objects.count() == 1, (
            "Tenant2 deve continuar com sua filial inicial intacta, "
            "mesmo após exclusão no tenant1."
        )
        logger.info(
            "Confirmação: tenant2 permanece com 1 filial após exclusão no tenant1."
        )
