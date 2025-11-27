# filial/tests/nfce/test_nfce_config_provider_api_externa.py

import logging

import pytest
from django.apps import apps
from django.core.exceptions import ValidationError
from django_tenants.utils import schema_context

from filial.models.filial_nfce_models import FilialNFCeConfig, NFCeProvider

logger = logging.getLogger(__name__)


@pytest.mark.django_db(transaction=True)
def test_nfce_config_provider_ndd_requer_campos_externos(two_tenants_with_admins):
    """
    Cenário:
    - No tenant1, pegamos a filial inicial (fixture two_tenants_with_admins).
    - Criamos FilialNFCeConfig com provider 'NDD':
        * Sem external_company_id / external_endpoint_base -> deve falhar no clean().
        * Com external_company_id / external_endpoint_base -> deve passar no clean().

    Objetivo:
    - Garantir que a model FilialNFCeConfig está preparada para integração
      com API externa (NDD) de forma consistente.
    """
    schema1 = two_tenants_with_admins["schema1"]
    FilialModel = apps.get_model("filial", "Filial")

    with schema_context(schema1):
        filial = FilialModel.objects.first()
        assert filial is not None, "Pré-condição: deve existir uma filial inicial no tenant1."

        # 1) Provider NDD sem campos externos -> ValidationError
        cfg_invalida = FilialNFCeConfig(
            filial=filial,
            ambiente=FilialNFCeConfig.AMBIENTE_HOMOLOGACAO,
            csc_id="000001",
            csc_token="TOKEN_NDD",
            provider=NFCeProvider.NDD,
            external_company_id=None,
            external_endpoint_base=None,
        )
        with pytest.raises(ValidationError):
            cfg_invalida.full_clean()

        # 2) Provider NDD com campos externos -> OK
        cfg_valida = FilialNFCeConfig(
            filial=filial,
            ambiente=FilialNFCeConfig.AMBIENTE_HOMOLOGACAO,
            csc_id="000002",
            csc_token="TOKEN_NDD_OK",
            provider=NFCeProvider.NDD,
            external_company_id="EMPRESA_NDD_123",
            external_endpoint_base="https://api-ndd.exemplo.com/nfce",
            external_api_key_alias="NDD_NFCE_T1",
        )
        # Não deve lançar ValidationError
        cfg_valida.full_clean()
        cfg_valida.save()

        assert FilialNFCeConfig.objects.filter(pk=cfg_valida.pk).exists()
        logger.info(
            "Config NFC-e com provider NDD criada com sucesso para filial_id=%s.",
            filial.id,
        )


@pytest.mark.django_db(transaction=True)
def test_nfce_config_provider_proprio_pode_ter_campos_externos_opcionais(
    two_tenants_with_admins,
):
    """
    Cenário:
    - No tenant1, usamos provider 'PROPRIO' (API própria).
    - external_company_id e external_endpoint_base podem ficar vazios,
      pois a API própria pode usar outra forma de parametrização.

    Objetivo:
    - Garantir que a model é flexível para outros providers.
    """
    schema1 = two_tenants_with_admins["schema1"]
    FilialModel = apps.get_model("filial", "Filial")

    with schema_context(schema1):
        filial = FilialModel.objects.first()

        cfg = FilialNFCeConfig(
            filial=filial,
            ambiente=FilialNFCeConfig.AMBIENTE_PRODUCAO,
            csc_id="000010",
            csc_token="TOKEN_PROPRIO",
            provider=NFCeProvider.PROPRIO,
            external_company_id=None,
            external_endpoint_base=None,
            external_api_key_alias=None,
        )

        # Não deve levantar ValidationError mesmo sem campos externos
        cfg.full_clean()
        cfg.save()

        assert FilialNFCeConfig.objects.filter(pk=cfg.pk).exists()
        logger.info(
            "Config NFC-e com provider 'PROPRIO' criada com sucesso para filial_id=%s.",
            filial.id,
        )


@pytest.mark.django_db(transaction=True)
def test_nfce_config_provider_multitenant_isolamento(two_tenants_with_admins):
    """
    Cenário:
    - Tenant1 e Tenant2 provisionados via two_tenants_with_admins.
    - No tenant1:
        * Criamos FilialNFCeConfig com provider NDD e um conjunto de dados.
    - No tenant2:
        * Criamos FilialNFCeConfig com provider NDD e OUTRO conjunto de dados.

    Verificamos:
    - Cada tenant enxerga apenas sua própria configuração.
    - Mesmo 'external_company_id' poderia teoricamente se repetir em tenants
      diferentes, mas aqui usamos valores distintos para ficar explícito.
    """
    schema1 = two_tenants_with_admins["schema1"]
    schema2 = two_tenants_with_admins["schema2"]

    FilialModel = apps.get_model("filial", "Filial")

    # Tenant1
    with schema_context(schema1):
        filial_t1 = FilialModel.objects.first()
        cfg_t1 = FilialNFCeConfig.objects.create(
            filial=filial_t1,
            ambiente=FilialNFCeConfig.AMBIENTE_HOMOLOGACAO,
            csc_id="T1CSC",
            csc_token="T1TOKEN",
            provider=NFCeProvider.NDD,
            external_company_id="EMPRESA_T1",
            external_endpoint_base="https://api-ndd.tenant1.com/nfce",
            external_api_key_alias="NDD_T1",
        )
        assert FilialNFCeConfig.objects.count() == 1
        logger.info(
            "Config NFC-e criada no tenant1: id=%s, external_company_id=%s",
            cfg_t1.pk,
            cfg_t1.external_company_id,
        )

    # Tenant2
    with schema_context(schema2):
        filial_t2 = FilialModel.objects.first()
        cfg_t2 = FilialNFCeConfig.objects.create(
            filial=filial_t2,
            ambiente=FilialNFCeConfig.AMBIENTE_PRODUCAO,
            csc_id="T2CSC",
            csc_token="T2TOKEN",
            provider=NFCeProvider.NDD,
            external_company_id="EMPRESA_T2",
            external_endpoint_base="https://api-ndd.tenant2.com/nfce",
            external_api_key_alias="NDD_T2",
        )
        assert FilialNFCeConfig.objects.count() == 1
        logger.info(
            "Config NFC-e criada no tenant2: id=%s, external_company_id=%s",
            cfg_t2.pk,
            cfg_t2.external_company_id,
        )

    # Verificar isolamento explícito
    with schema_context(schema1):
        cfgs_t1 = list(FilialNFCeConfig.objects.all())
        assert len(cfgs_t1) == 1
        assert cfgs_t1[0].external_company_id == "EMPRESA_T1"

    with schema_context(schema2):
        cfgs_t2 = list(FilialNFCeConfig.objects.all())
        assert len(cfgs_t2) == 1
        assert cfgs_t2[0].external_company_id == "EMPRESA_T2"


@pytest.mark.django_db(transaction=True)
def test_edicao_nfce_config_um_tenant_nao_afeta_outro(two_tenants_with_admins):
    """
    Cenário:
    - Criamos uma FilialNFCeConfig em cada tenant com provider NDD.
    - No tenant1, editamos endpoint/alias.
    - No tenant2, os dados devem permanecer intactos.

    Objetivo:
    - Garantir isolamento de edição entre tenants para as configs NFC-e.
    """
    schema1 = two_tenants_with_admins["schema1"]
    schema2 = two_tenants_with_admins["schema2"]

    FilialModel = apps.get_model("filial", "Filial")

    # Criar configs em cada tenant
    with schema_context(schema1):
        filial_t1 = FilialModel.objects.first()
        cfg_t1 = FilialNFCeConfig.objects.create(
            filial=filial_t1,
            ambiente=FilialNFCeConfig.AMBIENTE_HOMOLOGACAO,
            csc_id="CSC_EDIT_T1",
            csc_token="TOKEN_EDIT_T1",
            provider=NFCeProvider.NDD,
            external_company_id="EMPRESA_EDIT_T1",
            external_endpoint_base="https://api-ndd.tenant1.com/nfce",
            external_api_key_alias="NDD_T1_OLD",
        )

    with schema_context(schema2):
        filial_t2 = FilialModel.objects.first()
        cfg_t2 = FilialNFCeConfig.objects.create(
            filial=filial_t2,
            ambiente=FilialNFCeConfig.AMBIENTE_HOMOLOGACAO,
            csc_id="CSC_EDIT_T2",
            csc_token="TOKEN_EDIT_T2",
            provider=NFCeProvider.NDD,
            external_company_id="EMPRESA_EDIT_T2",
            external_endpoint_base="https://api-ndd.tenant2.com/nfce",
            external_api_key_alias="NDD_T2",
        )

    # Editar apenas no tenant1
    with schema_context(schema1):
        cfg_t1.external_endpoint_base = "https://api-ndd.tenant1.com/nfce/v2"
        cfg_t1.external_api_key_alias = "NDD_T1_NEW"
        cfg_t1.save(update_fields=["external_endpoint_base", "external_api_key_alias"])

        cfg_t1_refresh = FilialNFCeConfig.objects.get(pk=cfg_t1.pk)
        assert cfg_t1_refresh.external_endpoint_base.endswith("/v2")
        assert cfg_t1_refresh.external_api_key_alias == "NDD_T1_NEW"

    # Garantir que tenant2 ficou intocado
    with schema_context(schema2):
        cfg_t2_refresh = FilialNFCeConfig.objects.get(pk=cfg_t2.pk)
        assert cfg_t2_refresh.external_endpoint_base == "https://api-ndd.tenant2.com/nfce"
        assert cfg_t2_refresh.external_api_key_alias == "NDD_T2"
