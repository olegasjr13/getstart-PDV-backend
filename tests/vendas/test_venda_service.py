import logging
from decimal import Decimal

from django.forms import ValidationError
import pytest
from django.apps import apps
from django_tenants.utils import schema_context

from fiscal.models.ncm_models import NCM
from produtos.models.grupo_produtos_models import GrupoProduto
from produtos.models.unidade_medidas_models import UnidadeMedida
from usuario.models.usuario_models import UserPerfil
from vendas.models.venda_models import TipoDocumentoFiscal, TipoVenda, VendaStatus

from vendas.services.exceptions import (
    DescontoRequerAutenticacaoOperadorError,
    DescontoRequerAprovadorError,
)
from vendas.services.vendas.abri_orcamento_service import abrir_orcamento
from vendas.services.vendas.abrir_venda_services import abrir_venda
from vendas.services.vendas.adicionar_item_service import adicionar_item
from vendas.services.vendas.alterar_quantidade_item_service import alterar_quantidade_item
from vendas.services.vendas.converter_orcamento_venda_service import converter_orcamento_em_venda
from vendas.services.vendas.limpar_carrinho_service import limpar_carrinho
from vendas.services.vendas.remover_item_service import remover_item


logger = logging.getLogger(__name__)


@pytest.mark.django_db(transaction=True)
def test_abrir_venda_inicia_com_totais_zero_e_status_aberta(two_tenants_with_admins):
    """
    Cenário:
    - Criar uma nova venda via VendaService.abrir_venda.

    Esperado:
    - status=ABERTA
    - totais = 0
    - sem itens
    """
    schema1 = two_tenants_with_admins["schema1"]

    FilialModel = apps.get_model("filial", "Filial")
    TerminalModel = apps.get_model("terminal", "Terminal")
    UserModel = apps.get_model("usuario", "User")
    VendaModel = apps.get_model("vendas", "Venda")

    with schema_context(schema1):
        filial = FilialModel.objects.first()
        operador = UserModel.objects.first()

        terminal = TerminalModel.objects.create(
            filial=filial,
            identificador="CX_CART_01",
            ativo=True,
        )

        logger.info("Abrindo nova venda para teste de abertura básica.")
        venda = abrir_venda(
            filial=filial,
            terminal=terminal,
            operador=operador,
        )

        assert venda.status == VendaStatus.ABERTA
        assert venda.total_bruto == Decimal("0.00")
        assert venda.total_desconto == Decimal("0.00")
        assert venda.total_liquido == Decimal("0.00")
        assert venda.itens.count() == 0

        logger.info(
            "Venda aberta. venda_id=%s, status=%s, total_bruto=%s, total_liquido=%s",
            venda.id,
            venda.status,
            venda.total_bruto,
            venda.total_liquido,
        )

        assert VendaModel.objects.count() == 1


@pytest.mark.django_db(transaction=True)
def test_adicionar_item_sem_desconto_atualiza_totais(two_tenants_with_admins):
    """
    Cenário:
    - Abrir venda.
    - Adicionar item sem desconto.

    Esperado:
    - total_bruto = soma dos itens
    - total_desconto = 0
    - total_liquido = total_bruto
    """
    schema1 = two_tenants_with_admins["schema1"]

    FilialModel = apps.get_model("filial", "Filial")
    TerminalModel = apps.get_model("terminal", "Terminal")
    UserModel = apps.get_model("usuario", "User")
    ProdutoModel = apps.get_model("produtos", "Produto")

    with schema_context(schema1):
        filial = FilialModel.objects.first()
        operador = UserModel.objects.first()
        terminal = TerminalModel.objects.create(
            filial=filial,
            identificador="CX_CART_02",
            ativo=True,
        )

        grupo_produto = GrupoProduto.objects.create(
            descricao="Grupo sem limite",
            ativo=True,
        )

        # Criar ncm basico
        ncm = NCM.objects.create(
            descricao="NCM basico",
            codigo="87089990",
            ativo=True
        )

        # Criar unidade comercial e tributavel basica
        unidade=UnidadeMedida.objects.create(
            descricao="Unidade",
            sigla="UN",
            ativo=True
        )

        produto = ProdutoModel.objects.create(
            descricao="Produto Carrinho 1",
            preco_venda=Decimal("20.00"),
            grupo=grupo_produto,
            ncm=ncm,
            unidade_comercial_id=unidade.id,
            unidade_tributavel_id=unidade.id,
            ativo=True,
        )

        venda = abrir_venda(
            filial=filial,
            terminal=terminal,
            operador=operador,
        )

        logger.info(
            "Adicionando item sem desconto. venda_id=%s, produto_id=%s, qtd=2, preco=20.00",
            venda.id,
            produto.id,
        )

        item = adicionar_item(
            venda=venda,
            produto=produto,
            quantidade=Decimal("2.000"),
            operador=operador,
        )

        venda.refresh_from_db()

        assert item.total_bruto == Decimal("40.00")
        assert item.percentual_desconto_aplicado in (None, Decimal("0.00"))
        assert item.total_liquido == Decimal("40.00")

        assert venda.total_bruto == Decimal("40.00")
        assert venda.total_desconto in (None,Decimal("0.00"))
        assert venda.total_liquido == Decimal("40.00")

        logger.info(
            "Item adicionado sem desconto. venda.total_bruto=%s, total_desconto=%s, total_liquido=%s",
            venda.total_bruto,
            venda.total_desconto,
            venda.total_liquido,
        )


@pytest.mark.django_db(transaction=True)
def test_adicionar_item_com_desconto_usa_regras_de_limite(two_tenants_with_admins):
    """
    Cenário:
    - Produto com limite 5%.
    - Operador com limite 10%.
    - Desconto solicitado = 5%.

    Esperado:
    - Desconto permitido sem senha (zona livre contexto).
    - Desconto aplicado corretamente no item e na venda.
    """
    schema1 = two_tenants_with_admins["schema1"]

    FilialModel = apps.get_model("filial", "Filial")
    TerminalModel = apps.get_model("terminal", "Terminal")
    UserModel = apps.get_model("usuario", "User")
    ProdutoModel = apps.get_model("produtos", "Produto")
    MotivoDescontoModel = apps.get_model("promocoes", "MotivoDesconto")

    with schema_context(schema1):
        filial = FilialModel.objects.first()
        operador = UserModel.objects.first()

        perfil = UserPerfil.objects.create(
            descricao="ADMIN",
            desconto_maximo_percentual=Decimal("10.00"),
        )
        operador.perfil = perfil
        operador.save(update_fields=["perfil"])

        terminal = TerminalModel.objects.create(
            filial=filial,
            identificador="CX_CART_03",
            ativo=True,
        )

        grupo_produto = GrupoProduto.objects.create(
            descricao="Grupo sem limite",
            ativo=True,
        )

        # Criar ncm basico
        ncm = NCM.objects.create(
            descricao="NCM basico",
            codigo="87089990",
            ativo=True
        )

        # Criar unidade comercial e tributavel basica
        unidade=UnidadeMedida.objects.create(
            descricao="Unidade",
            sigla="UN",
            ativo=True
        )


        produto = ProdutoModel.objects.create(
            descricao="Produto Carrinho 2",
            preco_venda=Decimal("100.00"),
            grupo=grupo_produto,
            ncm=ncm,
            unidade_comercial_id=unidade.id,
            unidade_tributavel_id=unidade.id,
            ativo=True,
        )
        if hasattr(produto, "desconto_maximo_percentual"):
            produto.desconto_maximo_percentual = Decimal("5.00")
            produto.save(update_fields=["desconto_maximo_percentual"])

        motivo = MotivoDescontoModel.objects.create(
            codigo="PROMO5_CART",
            descricao="Desconto 5% no carrinho (zona livre).",
        )

        venda = abrir_venda(
            filial=filial,
            terminal=terminal,
            operador=operador,
        )

        logger.info(
            "Adicionando item com desconto de 5%% (<= limite contexto=5%%). "
            "Esperado: sem senha, apenas motivo."
        )

        item = adicionar_item(
            venda=venda,
            produto=produto,
            quantidade=Decimal("1.000"),
            operador=operador,
            motivo_desconto=motivo,
            percentual_desconto=Decimal("5.00"),
        )

        venda.refresh_from_db()

        assert item.percentual_desconto_aplicado == Decimal("5.00")
        #assert item.desconto in Decimal("5.00")
        assert item.total_liquido == Decimal("95.00")

        assert venda.total_bruto == Decimal("100.00")
        assert venda.total_desconto == Decimal("5.00")
        assert venda.total_liquido == Decimal("95.00")

        logger.info(
            "Item com desconto de 5%% adicionado. venda.total_bruto=%s, total_desconto=%s, total_liquido=%s",
            venda.total_bruto,
            venda.total_desconto,
            venda.total_liquido,
        )


@pytest.mark.django_db(transaction=True)
def test_adicionar_item_com_desconto_na_faixa_operador_requer_senha(two_tenants_with_admins):
    """
    Cenário:
    - Produto limite 5%.
    - Operador limite 10%.
    - Desconto solicitado = 8% (entre contexto e operador).

    Esperado:
    - Primeiro chamada SEM operador_autenticado -> DescontoRequerAutenticacaoOperadorError.
    - Segunda chamada COM operador_autenticado=True -> desconto aplicado.
    """
    schema1 = two_tenants_with_admins["schema1"]

    FilialModel = apps.get_model("filial", "Filial")
    TerminalModel = apps.get_model("terminal", "Terminal")
    UserModel = apps.get_model("usuario", "User")
    ProdutoModel = apps.get_model("produtos", "Produto")
    MotivoDescontoModel = apps.get_model("promocoes", "MotivoDesconto")

    with schema_context(schema1):
        filial = FilialModel.objects.first()
        operador = UserModel.objects.first()

        perfil = UserPerfil.objects.create(
            descricao="ADMIN",
            desconto_maximo_percentual=Decimal("10.00"),
        )
        operador.perfil = perfil
        operador.save(update_fields=["perfil"])

        terminal = TerminalModel.objects.create(
            filial=filial,
            identificador="CX_CART_04",
            ativo=True,
        )

        grupo_produto = GrupoProduto.objects.create(
            descricao="Grupo sem limite",
            ativo=True,
        )

        # Criar ncm basico
        ncm = NCM.objects.create(
            descricao="NCM basico",
            codigo="87089990",
            ativo=True
        )

        # Criar unidade comercial e tributavel basica
        unidade=UnidadeMedida.objects.create(
            descricao="Unidade",
            sigla="UN",
            ativo=True
        )

        produto = ProdutoModel.objects.create(
            descricao="Produto Carrinho 3",
            preco_venda=Decimal("100.00"),
            grupo=grupo_produto,
            ncm=ncm,
            unidade_comercial_id=unidade.id,
            unidade_tributavel_id=unidade.id,
            ativo=True,
        )
        if hasattr(produto, "desconto_maximo_percentual"):
            produto.desconto_maximo_percentual = Decimal("5.00")
            produto.save(update_fields=["desconto_maximo_percentual"])

        motivo = MotivoDescontoModel.objects.create(
            codigo="DESC8_CART",
            descricao="Desconto 8% exige senha operador.",
        )

        venda = abrir_venda(
            filial=filial,
            terminal=terminal,
            operador=operador,
        )

        logger.info(
            "Tentando adicionar item com desconto de 8%% sem operador_autenticado. "
            "Esperado: erro solicitando senha do operador."
        )

        with pytest.raises(DescontoRequerAutenticacaoOperadorError) as exc:
            adicionar_item(
                venda=venda,
                produto=produto,
                quantidade=Decimal("1.000"),
                operador=operador,
                motivo_desconto=motivo,
                percentual_desconto=Decimal("8.00"),
                operador_autenticado=False,
            )
        logger.info(
            "Erro esperado recebido: %s (percentual_solicitado=%s, limite_operador=%s)",
            exc.value.mensagem,
            exc.value.percentual_solicitado,
            exc.value.limite_operador,
        )

        logger.info(
            "Repetindo adição do item com operador_autenticado=True. "
            "Esperado: desconto aplicado com sucesso."
        )

        item = adicionar_item(
            venda=venda,
            produto=produto,
            quantidade=Decimal("1.000"),
            operador=operador,
            motivo_desconto=motivo,
            percentual_desconto=Decimal("8.00"),
            operador_autenticado=True,
        )

        venda.refresh_from_db()

        assert item.percentual_desconto_aplicado == Decimal("8.00")
        #assert item.desconto == Decimal("8.00")
        assert item.total_liquido == Decimal("92.00")

        assert venda.total_desconto == Decimal("8.00")
        assert venda.total_liquido == Decimal("92.00")

        logger.info(
            "Item com desconto de 8%% adicionado após autenticação do operador. "
            "venda.total_desconto=%s, total_liquido=%s",
            venda.total_desconto,
            venda.total_liquido,
        )


@pytest.mark.django_db(transaction=True)
def test_alterar_quantidade_item_mantem_percentual_desconto(two_tenants_with_admins):
    """
    Cenário:
    - Adiciona item com desconto de 5%.
    - Altera quantidade de 1 para 2.

    Esperado:
    - Percentual de desconto permanece 5%.
    - Valores de desconto e totais são recalculados proporcionalmente.
    """
    schema1 = two_tenants_with_admins["schema1"]

    FilialModel = apps.get_model("filial", "Filial")
    TerminalModel = apps.get_model("terminal", "Terminal")
    UserModel = apps.get_model("usuario", "User")
    ProdutoModel = apps.get_model("produtos", "Produto")
    MotivoDescontoModel = apps.get_model("promocoes", "MotivoDesconto")

    with schema_context(schema1):
        filial = FilialModel.objects.first()
        operador = UserModel.objects.first()

        perfil = UserPerfil.objects.create(
            descricao="ADMIN",
            desconto_maximo_percentual=Decimal("10.00"),
        )
        operador.perfil = perfil
        operador.save(update_fields=["perfil"])

        terminal = TerminalModel.objects.create(
            filial=filial,
            identificador="CX_CART_05",
            ativo=True,
        )

        grupo_produto = GrupoProduto.objects.create(
            descricao="Grupo sem limite",
            ativo=True,
        )

        # Criar ncm basico
        ncm = NCM.objects.create(
            descricao="NCM basico",
            codigo="87089990",
            ativo=True
        )

        # Criar unidade comercial e tributavel basica
        unidade=UnidadeMedida.objects.create(
            descricao="Unidade",
            sigla="UN",
            ativo=True
        )

        produto = ProdutoModel.objects.create(
            descricao="Produto Carrinho 4",
            preco_venda=Decimal("100.00"),
            grupo=grupo_produto,
            ncm=ncm,
            unidade_comercial_id=unidade.id,
            unidade_tributavel_id=unidade.id,
            ativo=True,
        )

        if hasattr(produto, "desconto_maximo_percentual"):
            produto.desconto_maximo_percentual = Decimal("5.00")
            produto.save(update_fields=["desconto_maximo_percentual"])

        motivo = MotivoDescontoModel.objects.create(
            codigo="DESC5_CART_QTD",
            descricao="Desconto 5% com alteração de quantidade.",
        )

        venda = abrir_venda(
            filial=filial,
            terminal=terminal,
            operador=operador,
        )

        logger.info("Adicionando item com desconto inicial de 5%%, qtd=1.")
        item = adicionar_item(
            venda=venda,
            produto=produto,
            quantidade=Decimal("1.000"),
            operador=operador,
            motivo_desconto=motivo,
            percentual_desconto=Decimal("5.00"),
        )

        venda.refresh_from_db()
        assert venda.total_liquido == Decimal("95.00")

        logger.info(
            "Alterando quantidade do item de 1 para 2. "
            "Esperado: manter 5%% de desconto."
        )

        item = alterar_quantidade_item(
            venda=venda,
            item=item,
            nova_quantidade=Decimal("2.00"),
            operador=operador,
            motivo_desconto=motivo,
        )

        venda.refresh_from_db()

        assert item.quantidade == Decimal("2.000")
        assert item.percentual_desconto_aplicado == Decimal("5.00")
        assert item.total_bruto == Decimal("200.00")
        #assert item.desconto == Decimal("10.00")
        assert item.total_liquido == Decimal("190.00")

        assert venda.total_bruto == Decimal("200.00")
        assert venda.total_desconto == Decimal("10.00")
        assert venda.total_liquido == Decimal("190.00")

        logger.info(
            "Quantidade alterada e desconto mantido em 5%%. "
            "venda.total_bruto=%s, total_desconto=%s, total_liquido=%s",
            venda.total_bruto,
            venda.total_desconto,
            venda.total_liquido,
        )


@pytest.mark.django_db(transaction=True)
def test_remover_item_e_limpar_carrinho_recalculam_totais(two_tenants_with_admins):
    """
    Cenário:
    - Adiciona dois itens.
    - Remove um item.
    - Limpa carrinho.

    Esperado:
    - Após remover 1 item -> totais recalculados.
    - Após limpar carrinho -> totais zerados, sem itens.
    """
    schema1 = two_tenants_with_admins["schema1"]

    FilialModel = apps.get_model("filial", "Filial")
    TerminalModel = apps.get_model("terminal", "Terminal")
    UserModel = apps.get_model("usuario", "User")
    ProdutoModel = apps.get_model("produtos", "Produto")

    with schema_context(schema1):
        filial = FilialModel.objects.first()
        operador = UserModel.objects.first()
        terminal = TerminalModel.objects.create(
            filial=filial,
            identificador="CX_CART_06",
            ativo=True,
        )

        grupo_produto = GrupoProduto.objects.create(
            descricao="Grupo sem limite",
            ativo=True,
        )

        # Criar ncm basico
        ncm = NCM.objects.create(
            descricao="NCM basico",
            codigo="87089990",
            ativo=True
        )

        # Criar unidade comercial e tributavel basica
        unidade=UnidadeMedida.objects.create(
            descricao="Unidade",
            sigla="UN",
            ativo=True
        )

        produto1 = ProdutoModel.objects.create(
            codigo_interno=1,
            descricao="Produto A",
            preco_venda=Decimal("10.00"),
            grupo=grupo_produto,
            ncm=ncm,
            unidade_comercial_id=unidade.id,
            unidade_tributavel_id=unidade.id,
            ativo=True,
        )
        produto2 = ProdutoModel.objects.create(
            codigo_interno=10,
            descricao="Produto B",
            preco_venda=Decimal("5.00"),
            grupo=grupo_produto,
            ncm=ncm,
            unidade_comercial_id=unidade.id,
            unidade_tributavel_id=unidade.id,
            ativo=True,
        )

        venda = abrir_venda(
            filial=filial,
            terminal=terminal,
            operador=operador,
        )

        logger.info("Adicionando dois itens no carrinho.")
        item1 = adicionar_item(
            venda=venda,
            produto=produto1,
            quantidade=Decimal("2.000"),  # 20
            operador=operador,
        )
        item2 = adicionar_item(
            venda=venda,
            produto=produto2,
            quantidade=Decimal("3.000"),  # 15
            operador=operador,
        )

        venda.refresh_from_db()
        assert venda.total_bruto == Decimal("35.00")
        assert venda.total_liquido == Decimal("35.00")

        logger.info("Removendo item2 e verificando recálculo dos totais.")
        remover_item(venda=venda, item=item2)

        venda.refresh_from_db()
        assert venda.total_bruto == Decimal("20.00")
        assert venda.total_liquido == Decimal("20.00")
        assert venda.itens.count() == 1

        logger.info("Limpando carrinho completamente.")
        limpar_carrinho(venda)

        venda.refresh_from_db()
        assert venda.total_bruto == Decimal("0.00")
        assert venda.total_desconto == Decimal("0.00")
        assert venda.total_liquido == Decimal("0.00")
        assert venda.itens.count() == 0

        logger.info(
            "Carrinho limpo. venda.total_bruto=%s, total_desconto=%s, total_liquido=%s, itens=%s",
            venda.total_bruto,
            venda.total_desconto,
            venda.total_liquido,
            venda.itens.count(),
        )

logger = logging.getLogger(__name__)


@pytest.mark.django_db(transaction=True)
def test_venda_cpf_na_nota_valido_e_normalizado(two_tenants_with_admins):
    """
    Cenário:
    - Abrir uma venda normal.
    - Informar um CPF válido com máscara (XXX.XXX.XXX-YY).
    - Chamar clean() e salvar.

    Esperado:
    - Venda aceita sem ValidationError.
    - Campo cpf_na_nota armazenado apenas com dígitos (sem máscara).
    """
    schema1 = two_tenants_with_admins["schema1"]

    FilialModel = apps.get_model("filial", "Filial")
    TerminalModel = apps.get_model("terminal", "Terminal")
    UserModel = apps.get_model("usuario", "User")
    VendaModel = apps.get_model("vendas", "Venda")

    with schema_context(schema1):
        filial = FilialModel.objects.first()
        operador = UserModel.objects.first()

        terminal = TerminalModel.objects.create(
            filial=filial,
            identificador="CX_CPF_01",
            ativo=True,
        )

        logger.info("Abrindo nova venda para testar CPF na nota.")
        venda = abrir_venda(
            filial=filial,
            terminal=terminal,
            operador=operador,
        )

        # CPF de exemplo válido
        cpf_mascarado = "111.444.777-35"
        venda.cpf_na_nota = cpf_mascarado

        logger.info("Chamando clean() na venda com cpf_na_nota=%s.", cpf_mascarado)
        venda.clean()
        venda.save(update_fields=["cpf_na_nota"])

        venda = VendaModel.objects.get(id=venda.id)

        logger.info("Verificando normalização do CPF armazenado. cpf_na_nota=%s", venda.cpf_na_nota)
        assert venda.cpf_na_nota == "11144477735"

@pytest.mark.django_db(transaction=True)
def test_venda_cpf_na_nota_invalido_dispara_validationerror(two_tenants_with_admins):
    """
    Cenário:
    - Abrir uma venda normal.
    - Informar um CPF inválido.
    - Chamar clean().

    Esperado:
    - ValidationError com mensagem associada a cpf_na_nota.
    """
    schema1 = two_tenants_with_admins["schema1"]

    FilialModel = apps.get_model("filial", "Filial")
    TerminalModel = apps.get_model("terminal", "Terminal")
    UserModel = apps.get_model("usuario", "User")

    with schema_context(schema1):
        filial = FilialModel.objects.first()
        operador = UserModel.objects.first()

        terminal = TerminalModel.objects.create(
            filial=filial,
            identificador="CX_CPF_02",
            ativo=True,
        )

        venda = abrir_venda(
            filial=filial,
            terminal=terminal,
            operador=operador,
        )

        cpf_invalido = "123.456.789-00"
        venda.cpf_na_nota = cpf_invalido

        logger.info(
            "Chamando clean() na venda com cpf_na_nota inválido=%s. "
            "Esperado: ValidationError.",
            cpf_invalido,
        )

        with pytest.raises(ValidationError) as exc:
            venda.clean()

        logger.info("ValidationError recebido: %s", exc.value)
        assert "cpf_na_nota" in exc.value.message_dict

@pytest.mark.django_db(transaction=True)
def test_venda_esta_aberta_para_pagamento_nao_permite_pagamento_em_processamento(two_tenants_with_admins):
    """
    Cenário:
    - Abrir venda normal.
    - Forçar transições de status:
        * ABERTA
        * AGUARDANDO_PAGAMENTO
        * PAGAMENTO_EM_PROCESSAMENTO

    Esperado:
    - ABERTA -> esta_aberta_para_pagamento == True
    - AGUARDANDO_PAGAMENTO -> True
    - PAGAMENTO_EM_PROCESSAMENTO -> False (novo comportamento desejado).
    """
    schema1 = two_tenants_with_admins["schema1"]

    FilialModel = apps.get_model("filial", "Filial")
    TerminalModel = apps.get_model("terminal", "Terminal")
    UserModel = apps.get_model("usuario", "User")

    with schema_context(schema1):
        filial = FilialModel.objects.first()
        operador = UserModel.objects.first()

        terminal = TerminalModel.objects.create(
            filial=filial,
            identificador="CX_STATUS_01",
            ativo=True,
        )

        venda = abrir_venda(
            filial=filial,
            terminal=terminal,
            operador=operador,
        )

        logger.info("Verificando esta_aberta_para_pagamento em status ABERTA.")
        assert venda.status == VendaStatus.ABERTA
        assert venda.esta_aberta_para_pagamento() is True

        logger.info("Alterando status para AGUARDANDO_PAGAMENTO.")
        venda.status = VendaStatus.AGUARDANDO_PAGAMENTO
        venda.save(update_fields=["status"])
        assert venda.esta_aberta_para_pagamento() is True

        logger.info("Alterando status para PAGAMENTO_EM_PROCESSAMENTO.")
        venda.status = VendaStatus.PAGAMENTO_EM_PROCESSAMENTO
        venda.save(update_fields=["status"])
        assert venda.esta_aberta_para_pagamento() is False

@pytest.mark.django_db(transaction=True)
def test_abrir_orcamento_cria_venda_tipo_orcamento_sem_documento_fiscal(two_tenants_with_admins):
    """
    Cenário:
    - Abrir um ORÇAMENTO via abrir_orcamento.

    Esperado:
    - tipo_venda = ORCAMENTO
    - documento_fiscal_tipo = NENHUM
    - status = ABERTA
    - totais zerados e sem itens.
    """
    schema1 = two_tenants_with_admins["schema1"]

    FilialModel = apps.get_model("filial", "Filial")
    TerminalModel = apps.get_model("terminal", "Terminal")
    UserModel = apps.get_model("usuario", "User")
    VendaModel = apps.get_model("vendas", "Venda")

    with schema_context(schema1):
        filial = FilialModel.objects.first()
        operador = UserModel.objects.first()

        terminal = TerminalModel.objects.create(
            filial=filial,
            identificador="CX_ORC_01",
            ativo=True,
        )

        logger.info("Abrindo ORÇAMENTO para teste.")
        venda = abrir_orcamento(
            filial=filial,
            terminal=terminal,
            operador=operador,
        )

        venda_db = VendaModel.objects.get(id=venda.id)

        assert venda_db.tipo_venda == TipoVenda.ORCAMENTO
        assert venda_db.documento_fiscal_tipo == TipoDocumentoFiscal.NENHUM
        assert venda_db.status == VendaStatus.ABERTA
        assert venda_db.total_bruto == Decimal("0.00")
        assert venda_db.total_desconto == Decimal("0.00")
        assert venda_db.total_liquido == Decimal("0.00")
        assert venda_db.itens.count() == 0

@pytest.mark.django_db(transaction=True)
def test_converter_orcamento_em_venda_normal_nfce(two_tenants_with_admins):
    """
    Cenário:
    - Abrir um ORÇAMENTO.
    - Converter em venda normal via converter_orcamento_em_venda.

    Esperado:
    - tipo_venda alterado para VENDA_NORMAL.
    - documento_fiscal_tipo alterado para NFCE (padrão).
    - status volta para ABERTA.
    """
    schema1 = two_tenants_with_admins["schema1"]

    FilialModel = apps.get_model("filial", "Filial")
    TerminalModel = apps.get_model("terminal", "Terminal")
    UserModel = apps.get_model("usuario", "User")

    with schema_context(schema1):
        filial = FilialModel.objects.first()
        operador = UserModel.objects.first()

        terminal = TerminalModel.objects.create(
            filial=filial,
            identificador="CX_ORC_02",
            ativo=True,
        )

        logger.info("Abrindo ORÇAMENTO para teste de conversão.")
        orcamento = abrir_orcamento(
            filial=filial,
            terminal=terminal,
            operador=operador,
        )

        logger.info("Convertendo ORÇAMENTO em venda normal.")
        venda_convertida = converter_orcamento_em_venda(venda=orcamento)

        assert venda_convertida.tipo_venda == TipoVenda.VENDA_NORMAL
        assert venda_convertida.documento_fiscal_tipo == TipoDocumentoFiscal.NFCE
        assert venda_convertida.status == VendaStatus.ABERTA
