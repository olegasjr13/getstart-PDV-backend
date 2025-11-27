# filial/tests/test_filial_casas_decimais_preco_display.py

import logging

import pytest
from django.apps import apps
from django_tenants.utils import schema_context

logger = logging.getLogger(__name__)


@pytest.mark.django_db(transaction=True)
def test_filial_casas_decimais_preco_display_default(two_tenants_with_admins):
    """
    Cenário:
    - Tenant inicial com uma filial provisionada.

    Esperado:
    - casas_decimais_preco_display == 2 (padrão).
    """
    schema1 = two_tenants_with_admins["schema1"]
    FilialModel = apps.get_model("filial", "Filial")

    with schema_context(schema1):
        filial = FilialModel.objects.first()
        assert filial is not None

        logger.info(
            "Verificando casas_decimais_preco_display na filial inicial. valor=%s",
            filial.casas_decimais_preco_display,
        )

        assert filial.casas_decimais_preco_display == 2
        if hasattr(filial, "get_casas_decimais_preco_display"):
            assert filial.get_casas_decimais_preco_display() == 2


@pytest.mark.django_db(transaction=True)
def test_filial_casas_decimais_preco_display_valores_validos(two_tenants_with_admins):
    """
    Cenário:
    - Criar novas filiais copiando o endereço da filial inicial.
    - Configurar casas_decimais_preco_display = 3 e 4.

    Esperado:
    - Campo aceita 3 e 4 sem erro.
    - Helper get_casas_decimais_preco_display (se existir) respeita limites [2,4].
    """
    schema1 = two_tenants_with_admins["schema1"]
    FilialModel = apps.get_model("filial", "Filial")

    with schema_context(schema1):
        filial_inicial = FilialModel.objects.first()
        assert filial_inicial is not None

        endereco_inicial = filial_inicial.endereco

        logger.info("Criando filial com casas_decimais_preco_display=3.")
        filial_3 = FilialModel.objects.create(
            razao_social="Filial 3 casas",
            nome_fantasia="Filial 3 casas",
            cnpj="11111111000100",
            ie="123456789012",
            im="",
            ativo=True,
            endereco=endereco_inicial,
            casas_decimais_preco_display=3,
        )

        logger.info("Criando filial com casas_decimais_preco_display=4.")
        filial_4 = FilialModel.objects.create(
            razao_social="Filial 4 casas",
            nome_fantasia="Filial 4 casas",
            cnpj="22222222000100",
            ie="987654321000",
            im="",
            ativo=True,
            endereco=endereco_inicial,
            casas_decimais_preco_display=4,
        )

        assert filial_3.casas_decimais_preco_display == 3
        assert filial_4.casas_decimais_preco_display == 4

        if hasattr(filial_3, "get_casas_decimais_preco_display"):
            assert filial_3.get_casas_decimais_preco_display() == 3
        if hasattr(filial_4, "get_casas_decimais_preco_display"):
            assert filial_4.get_casas_decimais_preco_display() == 4
