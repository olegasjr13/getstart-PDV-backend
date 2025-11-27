import logging

import pytest
from django.apps import apps
from django.db import IntegrityError
from django_tenants.utils import schema_context

from metodoPagamento.models.metodo_pagamento_models import MetodoPagamentoTipo

logger = logging.getLogger(__name__)


@pytest.mark.django_db(transaction=True)
def test_criar_filial_metodo_pagamento_somente_no_tenant1(two_tenants_with_admins):
    """
    Cenário:

    - Tenant 1 e Tenant 2 já provisionados via fixture two_tenants_with_admins.

    - No tenant1:
        * Criamos um MetodoPagamento.
        * Vinculamos esse MetodoPagamento a uma Filial via FilialMetodoPagamento.

    Verificamos:

    - A relação FilialMetodoPagamento existe apenas no tenant1.
    - No tenant2 NÃO existe nenhuma relação com o mesmo metodo_pagamento.codigo.
    """
    schema1 = two_tenants_with_admins["schema1"]
    schema2 = two_tenants_with_admins["schema2"]

    FilialModel = apps.get_model("filial", "Filial")
    MetodoPagamentoModel = apps.get_model("metodoPagamento", "MetodoPagamento")
    FilialMetodoPagamentoModel = apps.get_model(
        "metodoPagamento", "FilialMetodoPagamento"
    )

    codigo_metodo = "DIN_T1"

    # ---------------------------
    # Tenant1: criar método e relação
    # ---------------------------
    with schema_context(schema1):
        filial_t1 = FilialModel.objects.first()
        assert filial_t1 is not None

        metodo = MetodoPagamentoModel.objects.create(
            codigo=codigo_metodo,
            tipo=MetodoPagamentoTipo.DINHEIRO,
            descricao="Dinheiro Tenant1",
            utiliza_tef=False,
            codigo_fiscal="01",
            codigo_tef=None,
            desconto_automatico_percentual=0.00,
            permite_parcelamento=False,
            max_parcelas=1,
            valor_minimo_parcela=None,
            permite_troco=True,
            ordem_exibicao=1,
            permite_desconto=True,
            ativo=True,
        )

        rel = FilialMetodoPagamentoModel.objects.create(
            filial=filial_t1,
            metodo_pagamento=metodo,
            ativo=True,
        )

        assert FilialMetodoPagamentoModel.objects.count() == 1
        logger.info(
            "Relação FilialMetodoPagamento criada no tenant1: filial=%s, metodo=%s",
            filial_t1.id,
            metodo.codigo,
        )

    # ---------------------------
    # Tenant2: não deve haver relação alguma
    # ---------------------------
    with schema_context(schema2):
        assert FilialMetodoPagamentoModel.objects.count() == 0, (
            "Tenant2 não deve ter nenhuma relação FilialMetodoPagamento "
            "quando criamos apenas no tenant1."
        )

        logger.info(
            "Confirmação: nenhuma FilialMetodoPagamento existe no tenant2 após criação no tenant1."
        )


@pytest.mark.django_db(transaction=True)
def test_mesma_combinacao_filial_metodo_pode_existir_em_tenants_diferentes(
    two_tenants_with_admins,
):
    """
    Garante que a combinação (filial, metodo_pagamento) é única apenas
    dentro do MESMO tenant (schema).

    Cenário:
    - No tenant1: criar MetodoPagamento com código X e vincular a filial.
    - No tenant2: criar MetodoPagamento com MESMO código X (instância própria do schema)
      e vincular a filial local.

    Esperado:
    - Ambas as relações são permitidas (schemas isolados).
    """
    schema1 = two_tenants_with_admins["schema1"]
    schema2 = two_tenants_with_admins["schema2"]

    FilialModel = apps.get_model("filial", "Filial")
    MetodoPagamentoModel = apps.get_model("metodoPagamento", "MetodoPagamento")
    FilialMetodoPagamentoModel = apps.get_model(
        "metodoPagamento", "FilialMetodoPagamento"
    )

    codigo_compartilhado = "CRC_X"

    # Tenant1
    with schema_context(schema1):
        filial_t1 = FilialModel.objects.first()
        metodo_t1 = MetodoPagamentoModel.objects.create(
            codigo=codigo_compartilhado,
            tipo=MetodoPagamentoTipo.CREDITO,
            descricao="Crédito Tenant1",
            utiliza_tef=True,
            codigo_fiscal="03",
            codigo_tef="CRED_T1",
            desconto_automatico_percentual=None,
            permite_parcelamento=True,
            max_parcelas=6,
            valor_minimo_parcela=10.00,
            permite_troco=False,
            ordem_exibicao=2,
            permite_desconto=True,
            ativo=True,
        )

        FilialMetodoPagamentoModel.objects.create(
            filial=filial_t1,
            metodo_pagamento=metodo_t1,
            ativo=True,
        )

        assert FilialMetodoPagamentoModel.objects.count() == 1

    # Tenant2
    with schema_context(schema2):
        filial_t2 = FilialModel.objects.first()
        metodo_t2 = MetodoPagamentoModel.objects.create(
            codigo=codigo_compartilhado,
            tipo=MetodoPagamentoTipo.CREDITO,
            descricao="Crédito Tenant2",
            utiliza_tef=True,
            codigo_fiscal="03",
            codigo_tef="CRED_T2",
            desconto_automatico_percentual=None,
            permite_parcelamento=True,
            max_parcelas=12,
            valor_minimo_parcela=5.00,
            permite_troco=False,
            ordem_exibicao=2,
            permite_desconto=True,
            ativo=True,
        )

        FilialMetodoPagamentoModel.objects.create(
            filial=filial_t2,
            metodo_pagamento=metodo_t2,
            ativo=True,
        )

        assert FilialMetodoPagamentoModel.objects.count() == 1

    logger.info(
        "Fim: mesma combinação 'conceitual' (filial local + metodo com mesmo código) "
        "é permitida em tenants distintos (isolamento OK)."
    )


@pytest.mark.django_db(transaction=True)
def test_nao_permite_duplicar_mesma_filial_metodo_no_mesmo_tenant(
    two_tenants_with_admins,
):
    """
    Cenário:

    - No tenant1:
        * Criamos um MetodoPagamento.
        * Criamos uma relação FilialMetodoPagamento com esse método.
        * Tentamos criar OUTRA relação com a MESMA filial e MESMO método.

    Esperado:
    - Levanta IntegrityError por causa da unique constraint (filial, metodo_pagamento).
    """
    schema1 = two_tenants_with_admins["schema1"]

    FilialModel = apps.get_model("filial", "Filial")
    MetodoPagamentoModel = apps.get_model("metodoPagamento", "MetodoPagamento")
    FilialMetodoPagamentoModel = apps.get_model(
        "metodoPagamento", "FilialMetodoPagamento"
    )

    with schema_context(schema1):
        filial = FilialModel.objects.first()
        metodo = MetodoPagamentoModel.objects.create(
            codigo="PIX_DUP",
            tipo=MetodoPagamentoTipo.PIX,
            descricao="PIX Duplicidade",
            utiliza_tef=False,
            codigo_fiscal="17",
            codigo_tef=None,
            desconto_automatico_percentual=None,
            permite_parcelamento=False,
            max_parcelas=1,
            valor_minimo_parcela=None,
            permite_troco=False,
            ordem_exibicao=3,
            permite_desconto=True,
            ativo=True,
        )

        FilialMetodoPagamentoModel.objects.create(
            filial=filial,
            metodo_pagamento=metodo,
            ativo=True,
        )

        assert FilialMetodoPagamentoModel.objects.count() == 1

        with pytest.raises(IntegrityError):
            FilialMetodoPagamentoModel.objects.create(
                filial=filial,
                metodo_pagamento=metodo,
                ativo=True,
            )

        logger.info(
            "IntegrityError corretamente levantado ao tentar duplicar "
            "a mesma combinação (filial, metodo_pagamento) no tenant1."
        )


@pytest.mark.django_db(transaction=True)
def test_exclusao_relacao_em_um_tenant_nao_afeta_outro(two_tenants_with_admins):
    """
    Cenário:

    - Criamos relações FilialMetodoPagamento em tenant1 e tenant2.
    - No tenant1, deletamos a relação.
    - No tenant2, a relação deve permanecer intacta.

    Objetivo:
    - Garantir isolamento de exclusão entre tenants.
    """
    schema1 = two_tenants_with_admins["schema1"]
    schema2 = two_tenants_with_admins["schema2"]

    FilialModel = apps.get_model("filial", "Filial")
    MetodoPagamentoModel = apps.get_model("metodoPagamento", "MetodoPagamento")
    FilialMetodoPagamentoModel = apps.get_model(
        "metodoPagamento", "FilialMetodoPagamento"
    )

    # Criar em ambos os tenants
    with schema_context(schema1):
        filial_t1 = FilialModel.objects.first()
        metodo_t1 = MetodoPagamentoModel.objects.create(
            codigo="CRC_T1",
            tipo=MetodoPagamentoTipo.CREDITO,
            descricao="Crédito T1",
            utiliza_tef=True,
            codigo_fiscal="03",
            codigo_tef="CRED_T1",
            desconto_automatico_percentual=None,
            permite_parcelamento=True,
            max_parcelas=6,
            valor_minimo_parcela=10.00,
            permite_troco=False,
            ordem_exibicao=2,
            permite_desconto=True,
            ativo=True,
        )
        rel_t1 = FilialMetodoPagamentoModel.objects.create(
            filial=filial_t1,
            metodo_pagamento=metodo_t1,
            ativo=True,
        )
        assert FilialMetodoPagamentoModel.objects.count() == 1

    with schema_context(schema2):
        filial_t2 = FilialModel.objects.first()
        metodo_t2 = MetodoPagamentoModel.objects.create(
            codigo="CRC_T2",
            tipo=MetodoPagamentoTipo.CREDITO,
            descricao="Crédito T2",
            utiliza_tef=True,
            codigo_fiscal="03",
            codigo_tef="CRED_T2",
            desconto_automatico_percentual=None,
            permite_parcelamento=True,
            max_parcelas=12,
            valor_minimo_parcela=5.00,
            permite_troco=False,
            ordem_exibicao=2,
            permite_desconto=True,
            ativo=True,
        )
        rel_t2 = FilialMetodoPagamentoModel.objects.create(
            filial=filial_t2,
            metodo_pagamento=metodo_t2,
            ativo=True,
        )
        assert FilialMetodoPagamentoModel.objects.count() == 1

    # Deletar apenas no tenant1
    with schema_context(schema1):
        rel_t1.delete()
        assert FilialMetodoPagamentoModel.objects.count() == 0

    # Conferir tenant2 intacto
    with schema_context(schema2):
        assert FilialMetodoPagamentoModel.objects.count() == 1
        assert FilialMetodoPagamentoModel.objects.filter(id=rel_t2.id).exists()
        logger.info(
            "Confirmação: relação FilialMetodoPagamento no tenant2 permaneceu após exclusão no tenant1."
        )
