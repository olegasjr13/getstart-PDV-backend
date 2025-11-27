# tef/tests/test_tef_config_multitenant.py

import logging

import pytest
from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django_tenants.utils import schema_context

from tef.models.tef_models import TefConfig, TefProvider

logger = logging.getLogger(__name__)


@pytest.mark.django_db(transaction=True)
def test_tef_config_sitef_requer_merchant_id(two_tenants_with_admins):
    """
    Cenário:
    - No tenant1, pegamos a filial inicial.
    - Criamos TefConfig com provider 'SITEF':
        * Sem merchant_id -> deve falhar no clean().
        * Com merchant_id -> deve passar.

    Objetivo:
    - Garantir que a model TefConfig exige merchant_id para SITEF.
    """
    schema1 = two_tenants_with_admins["schema1"]
    FilialModel = apps.get_model("filial", "Filial")

    with schema_context(schema1):
        filial = FilialModel.objects.first()
        assert filial is not None

        # 1) Provider SITEF sem merchant_id -> ValidationError
        cfg_invalida = TefConfig(
            filial=filial,
            terminal=None,
            provider=TefProvider.SITEF,
            merchant_id="",  # vazio
        )
        with pytest.raises(ValidationError):
            cfg_invalida.full_clean()

        # 2) Provider SITEF com merchant_id -> OK
        cfg_valida = TefConfig(
            filial=filial,
            terminal=None,
            provider=TefProvider.SITEF,
            merchant_id="MERCHANT_T1",
            store_id="LOJA_01",
            endpoint_base="https://tef.tenant1.com/api",
            api_key_alias="TEF_T1",
            ativo=True,
        )
        cfg_valida.full_clean()
        cfg_valida.save()

        assert TefConfig.objects.filter(pk=cfg_valida.pk).exists()
        logger.info(
            "TefConfig SITEF criada com sucesso para filial_id=%s.",
            filial.id,
        )


@pytest.mark.django_db(transaction=True)
def test_tef_config_terminal_deve_pertencer_a_mesma_filial(two_tenants_with_admins):
    """
    Cenário:
    - No tenant1, criamos duas filiais (ou usamos a inicial + uma extra)
      e um terminal na filial inicial.
    - Tentamos criar TefConfig vinculando a outra filial com o terminal
      da filial inicial.

    Esperado:
    - ValidationError, pois terminal não pertence à mesma filial.
    """
    schema1 = two_tenants_with_admins["schema1"]
    FilialModel = apps.get_model("filial", "Filial")
    TerminalModel = apps.get_model("terminal", "Terminal")

    with schema_context(schema1):
        filial1 = FilialModel.objects.first()

        # Cria segunda filial simples usando o mesmo endereço só para o teste
        endereco = filial1.endereco
        filial2 = FilialModel.objects.create(
            razao_social="Filial 2 TEF",
            nome_fantasia="Loja TEF 2",
            cnpj="99999999000100",
            endereco=endereco,
            ativo=True,
        )

        terminal_filial1 = TerminalModel.objects.create(
            filial=filial1,
            identificador="CX01",
            ativo=True,
        )

        cfg = TefConfig(
            filial=filial2,              # filial 2
            terminal=terminal_filial1,   # terminal da filial 1
            provider=TefProvider.SITEF,
            merchant_id="MERCHANT_X",
        )

        with pytest.raises(ValidationError):
            cfg.full_clean()

        logger.info(
            "Validação correta: não permitiu TefConfig com terminal de outra filial."
        )


@pytest.mark.django_db(transaction=True)
def test_tef_config_multitenant_isolamento(two_tenants_with_admins):
    """
    Cenário:
    - Tenant1 e Tenant2 com filiais iniciais.
    - Criamos TefConfig SITEF em cada tenant com dados distintos.

    Esperado:
    - Cada tenant enxerga apenas a sua configuração.
    """
    schema1 = two_tenants_with_admins["schema1"]
    schema2 = two_tenants_with_admins["schema2"]

    FilialModel = apps.get_model("filial", "Filial")

    # Tenant1
    with schema_context(schema1):
        filial_t1 = FilialModel.objects.first()
        cfg_t1 = TefConfig.objects.create(
            filial=filial_t1,
            terminal=None,
            provider=TefProvider.SITEF,
            merchant_id="MERCHANT_T1",
            store_id="LOJA_T1",
            endpoint_base="https://tef.tenant1.com/api",
            api_key_alias="TEF_T1",
            ativo=True,
        )
        assert TefConfig.objects.count() == 1

    # Tenant2
    with schema_context(schema2):
        filial_t2 = FilialModel.objects.first()
        cfg_t2 = TefConfig.objects.create(
            filial=filial_t2,
            terminal=None,
            provider=TefProvider.SITEF,
            merchant_id="MERCHANT_T2",
            store_id="LOJA_T2",
            endpoint_base="https://tef.tenant2.com/api",
            api_key_alias="TEF_T2",
            ativo=True,
        )
        assert TefConfig.objects.count() == 1

    # Verificar isolamento explícito
    with schema_context(schema1):
        cfgs_t1 = list(TefConfig.objects.all())
        assert len(cfgs_t1) == 1
        assert cfgs_t1[0].merchant_id == "MERCHANT_T1"

    with schema_context(schema2):
        cfgs_t2 = list(TefConfig.objects.all())
        assert len(cfgs_t2) == 1
        assert cfgs_t2[0].merchant_id == "MERCHANT_T2"


@pytest.mark.django_db(transaction=True)
def test_tef_config_unique_por_filial_terminal_provider(two_tenants_with_admins):
    """
    Cenário:
    - No tenant1, criamos duas configs:
        * Uma padrão (terminal=None)
        * Uma específica para terminal CX01
    - Tentamos duplicar mesma combinação (filial, terminal, provider).

    Esperado:
    - Permitir:
        * (filial, NULL, provider)
        * (filial, terminal, provider)
    - NÃO permitir duplicar (filial, terminal, provider) exatamente igual.
    """
    schema1 = two_tenants_with_admins["schema1"]
    FilialModel = apps.get_model("filial", "Filial")
    TerminalModel = apps.get_model("terminal", "Terminal")

    with schema_context(schema1):
        filial = FilialModel.objects.first()
        terminal = TerminalModel.objects.create(
            filial=filial,
            identificador="CX01",
            ativo=True,
        )

        # Config padrão (sem terminal)
        TefConfig.objects.create(
            filial=filial,
            terminal=None,
            provider=TefProvider.SITEF,
            merchant_id="MERCHANT_PADRAO",
            ativo=True,
        )

        # Config específica para terminal
        TefConfig.objects.create(
            filial=filial,
            terminal=terminal,
            provider=TefProvider.SITEF,
            merchant_id="MERCHANT_TERMINAL",
            ativo=True,
        )

        assert TefConfig.objects.count() == 2

        # Tentar duplicar config do terminal para o mesmo provider
        with pytest.raises(IntegrityError):
            TefConfig.objects.create(
                filial=filial,
                terminal=terminal,
                provider=TefProvider.SITEF,
                merchant_id="MERCHANT_DUPLICADO",
                ativo=True,
            )
