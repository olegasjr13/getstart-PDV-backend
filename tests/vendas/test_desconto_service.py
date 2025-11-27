import logging
from decimal import Decimal

import pytest
from django.apps import apps
from django_tenants.utils import schema_context

from fiscal.models.ncm_models import NCM
from produtos.models.grupo_produtos_models import GrupoProduto
from produtos.models.unidade_medidas_models import UnidadeMedida
from usuario.models.usuario_models import UserPerfil
from vendas.services.desconto_service import DescontoService
from vendas.services.exceptions import (
    DescontoNaoPermitidoError,
    DescontoRequerAutenticacaoOperadorError,
    DescontoRequerAprovadorError,
    MotivoDescontoObrigatorioError,
)

logger = logging.getLogger(__name__)


@pytest.mark.django_db(transaction=True)
def test_desconto_negado_quando_nenhum_limite_configurado(two_tenants_with_admins):
    """
    Cenário:
    - Nenhum limite de desconto configurado em:
        * Produto
        * Método de pagamento
        * Terminal
        * Filial
        * Operador
        * Aprovador (não informado)

    Esperado:
    - Qualquer tentativa de desconto > 0 deve ser NEGADA
      com DescontoNaoPermitidoError.
    """
    schema1 = two_tenants_with_admins["schema1"]

    FilialModel = apps.get_model("filial", "Filial")
    TerminalModel = apps.get_model("terminal", "Terminal")
    ProdutoModel = apps.get_model("produtos", "Produto")
    UserModel = apps.get_model("usuario", "User")
    VendaModel = apps.get_model("vendas", "Venda")
    VendaItemModel = apps.get_model("vendas", "VendaItem")
    MotivoDescontoModel = apps.get_model("promocoes", "MotivoDesconto")

    with schema_context(schema1):
        logger.info("Iniciando teste: nenhum limite configurado para desconto.")

        filial = FilialModel.objects.first()
        assert filial is not None

        # Garantir que filial não tem limite
        filial.desconto_maximo_percentual = None
        filial.save(update_fields=["desconto_maximo_percentual"])

        perfil = UserPerfil.objects.create(
            descricao="ADMIN",
            desconto_maximo_percentual=0.00,
        )

        operador = UserModel.objects.create(
            username="operador_sem_limite",
            email="operador_sem_limite@localhost",  
            perfil=perfil,
        )

        terminal = TerminalModel.objects.create(
            filial=filial,
            identificador="CX_DESC_01",
            ativo=True,
        )
        terminal.desconto_maximo_percentual = None
        terminal.save(update_fields=["desconto_maximo_percentual"])

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
            descricao="Produto sem limite",
            preco_venda=Decimal("10.00"),
            grupo=grupo_produto,
            ncm_id=ncm.id,
            unidade_comercial_id=unidade.id,
            unidade_tributavel_id=unidade.id,
            ativo=True,
        )
        # Sem limite de desconto no produto
        if hasattr(produto, "desconto_maximo_percentual"):
            produto.desconto_maximo_percentual = None
            produto.save(update_fields=["desconto_maximo_percentual"])

        venda = VendaModel.objects.create(
            filial=filial,
            terminal=terminal,
            operador=operador,
            total_bruto=Decimal("10.00"),
            total_desconto=Decimal("0.00"),
            total_liquido=Decimal("10.00"),
        )

        item = VendaItemModel.objects.create(
            venda=venda,
            produto=produto,
            descricao=produto.descricao,
            quantidade=Decimal("1.000"),
            preco_unitario=Decimal("10.000000"),
            total_bruto=Decimal("10.00"),
            percentual_desconto_aplicado=Decimal("0.00"),
            total_liquido=Decimal("10.00"),
        )

        motivo = MotivoDescontoModel.objects.create(
            codigo="SEM_LIMITE",
            descricao="Tentativa de desconto sem nenhum limite configurado.",
        )

        logger.info(
            "Tentando aplicar desconto de 5%% sem nenhum limite configurado "
            "(produto, método, terminal, filial, operador)."
        )

        with pytest.raises(DescontoNaoPermitidoError) as exc:
            DescontoService.aplicar_desconto_item(
                venda=venda,
                item=item,
                percentual_desconto_aplicado=Decimal("5.00"),
                operador=operador,
                motivo=motivo,
                metodo_pagamento=None,
            )

        logger.info(
            "Erro esperado recebido: %s (percentual_solicitado=%s)",
            exc.value.mensagem,
            exc.value.percentual_solicitado,
        )


@pytest.mark.django_db(transaction=True)
def test_desconto_ate_limite_contexto_sem_senha_somente_motivo(two_tenants_with_admins):
    """
    Cenário:
    - Produto com limite de desconto = 5%.
    - Operador com limite = 10% (maior que o contexto).
    - Desconto solicitado = 3%.

    Regras:
    - Zona até limite de contexto (5%) é 'livre':
        * NÃO exige senha.
        * Exige APENAS motivo.
    """
    schema1 = two_tenants_with_admins["schema1"]

    FilialModel = apps.get_model("filial", "Filial")
    TerminalModel = apps.get_model("terminal", "Terminal")
    ProdutoModel = apps.get_model("produtos", "Produto")
    UserModel = apps.get_model("usuario", "User")
    VendaModel = apps.get_model("vendas", "Venda")
    VendaItemModel = apps.get_model("vendas", "VendaItem")
    MotivoDescontoModel = apps.get_model("promocoes", "MotivoDesconto")

    with schema_context(schema1):
        logger.info("Iniciando teste: desconto até limite de contexto (5%%) sem senha.")

        filial = FilialModel.objects.first()
        operador = UserModel.objects.first()

        perfil = UserPerfil.objects.create(
            descricao="ADMIN",
            desconto_maximo_percentual=Decimal("10.00"),
        )

        operador = UserModel.objects.create(
            username="Operador",
            email="operador@localhost",  
            perfil=perfil,
        )

        terminal = TerminalModel.objects.create(
            filial=filial,
            identificador="CX_DESC_02",
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
            descricao="Produto com limite 5%",
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

        venda = VendaModel.objects.create(
            filial=filial,
            terminal=terminal,
            operador=operador,
            total_bruto=Decimal("100.00"),
            total_desconto=Decimal("0.00"),
            total_liquido=Decimal("100.00"),
        )

        item = VendaItemModel.objects.create(
            venda=venda,
            produto=produto,
            descricao=produto.descricao,
            quantidade=Decimal("1.000"),
            preco_unitario=Decimal("100.000000"),
            total_bruto=Decimal("100.00"),
            percentual_desconto_aplicado=Decimal("0.00"),
            total_liquido=Decimal("100.00"),
        )

        motivo = MotivoDescontoModel.objects.create(
            codigo="PROMO3",
            descricao="Desconto promocional de 3%.",
        )

        logger.info(
            "Aplicando desconto de 3%% (<= 5%% limite contexto). "
            "Esperado: permitido, sem senha, exigindo apenas motivo."
        )

        item_atualizado = DescontoService.aplicar_desconto_item(
            venda=venda,
            item=item,
            percentual_desconto_aplicado=Decimal("3.00"),
            operador=operador,
            motivo=motivo,
            metodo_pagamento=None,
            operador_autenticado=False,  # não precisa
            aprovador=None,
            aprovador_autenticado=False,
        )

        assert item_atualizado.percentual_desconto_aplicado == Decimal("3.00")
        assert item_atualizado.motivo_desconto == motivo
        assert item_atualizado.percentual_desconto_aplicado > 0
        assert item_atualizado.total_liquido == Decimal("97.00")

        venda.refresh_from_db()
        assert venda.total_desconto == Decimal("3.00")
        assert venda.total_liquido == Decimal("97.00")

        logger.info(
            "Desconto aplicado com sucesso: desconto=%s, total_liquido=%s",
            item_atualizado.percentual_desconto_aplicado,
            item_atualizado.total_liquido,
        )


@pytest.mark.django_db(transaction=True)
def test_desconto_acima_contexto_ate_operador_requer_senha_operador(two_tenants_with_admins):
    """
    Cenário:
    - Produto com limite de contexto = 5%.
    - Operador com limite de perfil = 10%.
    - Desconto solicitado = 8%.

    Regras:
    - 0..5%  -> zona livre (só motivo).
    - 5..10% -> zona do operador:
        * Exige senha/autenticação do operador.
    """
    schema1 = two_tenants_with_admins["schema1"]

    FilialModel = apps.get_model("filial", "Filial")
    TerminalModel = apps.get_model("terminal", "Terminal")
    ProdutoModel = apps.get_model("produtos", "Produto")
    UserModel = apps.get_model("usuario", "User")
    VendaModel = apps.get_model("vendas", "Venda")
    VendaItemModel = apps.get_model("vendas", "VendaItem")
    MotivoDescontoModel = apps.get_model("promocoes", "MotivoDesconto")

    with schema_context(schema1):
        filial = FilialModel.objects.first()
        operador = UserModel.objects.first()

        perfil = UserPerfil.objects.create(
            descricao="ADMIN",
            desconto_maximo_percentual=Decimal("10.00"),
        )

        operador = UserModel.objects.create(
            username="Operador",
            email="operador@localhost",  
            perfil=perfil,
        )

        terminal = TerminalModel.objects.create(
            filial=filial,
            identificador="CX_DESC_03",
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
            descricao="Produto com limite 5%",
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

        venda = VendaModel.objects.create(
            filial=filial,
            terminal=terminal,
            operador=operador,
            total_bruto=Decimal("100.00"),
            total_desconto=Decimal("0.00"),
            total_liquido=Decimal("100.00"),
        )

        item = VendaItemModel.objects.create(
            venda=venda,
            produto=produto,
            descricao=produto.descricao,
            quantidade=Decimal("1.000"),
            preco_unitario=Decimal("100.000000"),
            total_bruto=Decimal("100.00"),
            percentual_desconto_aplicado=Decimal("0.00"),
            total_liquido=Decimal("100.00"),
        )

        motivo = MotivoDescontoModel.objects.create(
            codigo="DESC8",
            descricao="Desconto 8% autorizado pelo operador.",
        )

        logger.info(
            "Tentando aplicar desconto de 8%% (>5%% limite contexto, <=10%% limite operador) "
            "SEM autenticação do operador. Esperado: erro solicitando senha do operador."
        )

        with pytest.raises(DescontoRequerAutenticacaoOperadorError) as exc:
            DescontoService.aplicar_desconto_item(
                venda=venda,
                item=item,
                percentual_desconto_aplicado=Decimal("8.00"),
                operador=operador,
                motivo=motivo,
                metodo_pagamento=None,
                operador_autenticado=False,
            )
        logger.info(
            "Erro esperado recebido: %s (percentual_solicitado=%s, limite_operador=%s)",
            exc.value.mensagem,
            exc.value.percentual_solicitado,
            exc.value.limite_operador,
        )

        logger.info(
            "Repetindo a tentativa, agora com operador_autenticado=True. "
            "Esperado: desconto permitido."
        )

        item_atualizado = DescontoService.aplicar_desconto_item(
            venda=venda,
            item=item,
            percentual_desconto_aplicado=Decimal("8.00"),
            operador=operador,
            motivo=motivo,
            metodo_pagamento=None,
            operador_autenticado=True,  # agora autenticado
        )

        assert item_atualizado.percentual_desconto_aplicado == Decimal("8.00")
        assert item_atualizado.desconto_aprovado_por == operador

        venda.refresh_from_db()
        assert venda.total_desconto == Decimal("8.00")
        assert venda.total_liquido == Decimal("92.00")

        logger.info(
            "Desconto de 8%% aplicado com sucesso após autenticação do operador. "
            "total_desconto=%s, total_liquido=%s",
            venda.total_desconto,
            venda.total_liquido,
        )


@pytest.mark.django_db(transaction=True)
def test_desconto_acima_operador_ate_aprovador_requer_aprovador(two_tenants_with_admins):
    """
    Cenário:
    - Produto com limite de contexto = 5%.
    - Operador com limite = 5%.
    - Aprovador (gerente) com limite = 12%.
    - Desconto solicitado = 10%.

    Regras:
    - Até 5%  -> zona livre (só motivo).
    - 5..10%  -> > limite operador => exige aprovador com limite >= 10%.
    """
    schema1 = two_tenants_with_admins["schema1"]

    FilialModel = apps.get_model("filial", "Filial")
    TerminalModel = apps.get_model("terminal", "Terminal")
    ProdutoModel = apps.get_model("produtos", "Produto")
    UserModel = apps.get_model("usuario", "User")
    VendaModel = apps.get_model("vendas", "Venda")
    VendaItemModel = apps.get_model("vendas", "VendaItem")
    MotivoDescontoModel = apps.get_model("promocoes", "MotivoDesconto")

    with schema_context(schema1):
        filial = FilialModel.objects.first()
        operador = UserModel.objects.first()

        perfil = UserPerfil.objects.create(
            descricao="ADMIN",
            desconto_maximo_percentual=Decimal("5.00"),
        )

        operador = UserModel.objects.create_user(
            username="Operador",
            email="operador@localhost", 
            password="123", 
            perfil=perfil,
        )

        perfil_gerente = UserPerfil.objects.create(
            descricao="GERENTE",
            desconto_maximo_percentual=Decimal("12.00"),
        )

        # Criar aprovador (pode ser clone do operador para o teste)
        aprovador = UserModel.objects.create_user(
            username="gerente_desc",
            email="gerente@example.com",
            password="1234",
        )
        aprovador.perfil = perfil_gerente
        aprovador.save(update_fields=["perfil"])

        print("Aprovador criado:", aprovador)
        print("Perfil aprovador criado:", aprovador.perfil)
        print("Operador criado:", operador)           
        terminal = TerminalModel.objects.create(
            filial=filial,
            identificador="CX_DESC_04",
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
            descricao="Produto com limite 5%",
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

        venda = VendaModel.objects.create(
            filial=filial,
            terminal=terminal,
            operador=operador,
            total_bruto=Decimal("100.00"),
            total_desconto=Decimal("0.00"),
            total_liquido=Decimal("100.00"),
        )

        item = VendaItemModel.objects.create(
            venda=venda,
            produto=produto,
            descricao=produto.descricao,
            quantidade=Decimal("1.000"),
            preco_unitario=Decimal("100.000000"),
            total_bruto=Decimal("100.00"),
            percentual_desconto_aplicado=Decimal("0.00"),
            total_liquido=Decimal("100.00"),
        )

        motivo = MotivoDescontoModel.objects.create(
            codigo="GER10",
            descricao="Desconto 10% autorizado pelo gerente.",
        )

        logger.info(
            "Tentando aplicar desconto de 10%% (>5%% limite operador, <=12%% limite aprovador) "
            "SEM informar aprovador. Esperado: erro solicitando aprovador."
        )

        with pytest.raises(DescontoRequerAprovadorError) as exc:
            DescontoService.aplicar_desconto_item(
                venda=venda,
                item=item,
                percentual_desconto_aplicado=Decimal("10.00"),
                operador=operador,
                motivo=motivo,
                metodo_pagamento=None,
                aprovador=None,
                aprovador_autenticado=False,
            )
        logger.info(
            "Erro esperado recebido (sem aprovador): %s (percentual_solicitado=%s)",
            exc.value.mensagem,
            exc.value.percentual_solicitado,
        )

        logger.info(
            "Repetindo tentativa com aprovador, porém sem aprovador_autenticado. "
            "Esperado: erro solicitando autenticação do aprovador."
        )
        print("Aprovador antes do erro:", aprovador)
        with pytest.raises(DescontoRequerAprovadorError) as exc2:
            DescontoService.aplicar_desconto_item(
                venda=venda,
                item=item,
                percentual_desconto_aplicado=Decimal("10.00"),
                operador=operador,
                motivo=motivo,
                metodo_pagamento=None,
                aprovador=aprovador,
                aprovador_autenticado=False,
            )
        logger.info(
            "Erro esperado recebido (aprovador não autenticado): %s",
            exc2.value.mensagem,
        )

        logger.info(
            "Repetindo tentativa com aprovador e aprovador_autenticado=True. "
            "Esperado: desconto permitido."
        )
        item_atualizado = DescontoService.aplicar_desconto_item(
            venda=venda,
            item=item,
            percentual_desconto_aplicado=Decimal("10.00"),
            operador=operador,
            motivo=motivo,
            metodo_pagamento=None,
            aprovador=aprovador,
            aprovador_autenticado=True,
        )

        assert item_atualizado.percentual_desconto_aplicado == Decimal("10.00")
        assert item_atualizado.desconto_aprovado_por == aprovador

        venda.refresh_from_db()
        assert venda.total_desconto == Decimal("10.00")
        assert venda.total_liquido == Decimal("90.00")

        logger.info(
            "Desconto de 10%% aplicado com sucesso após aprovação do gerente. "
            "total_desconto=%s, total_liquido=%s",
            venda.total_desconto,
            venda.total_liquido,
        )


@pytest.mark.django_db(transaction=True)
def test_desconto_acima_todos_limites_proibido(two_tenants_with_admins):
    """
    Cenário:
    - Produto limite = 5%.
    - Operador limite = 8%.
    - Aprovador limite = 12%.
    - Desconto solicitado = 20%.

    Esperado:
    - Desconto proibido (DescontoNaoPermitidoError),
      pois excede todos os limites.
    """
    schema1 = two_tenants_with_admins["schema1"]

    FilialModel = apps.get_model("filial", "Filial")
    TerminalModel = apps.get_model("terminal", "Terminal")
    ProdutoModel = apps.get_model("produtos", "Produto")
    UserModel = apps.get_model("usuario", "User")
    VendaModel = apps.get_model("vendas", "Venda")
    VendaItemModel = apps.get_model("vendas", "VendaItem")
    MotivoDescontoModel = apps.get_model("promocoes", "MotivoDesconto")

    with schema_context(schema1):
        filial = FilialModel.objects.first()
        operador = UserModel.objects.first()
        perfil = UserPerfil.objects.create(
            descricao="ADMIN",
            desconto_maximo_percentual=Decimal("8.00"),
        )

        operador = UserModel.objects.create(
            username="Operador",
            email="operador@localhost",  
            perfil=perfil,
        )

        perfil_gerente = UserPerfil.objects.create(
            descricao="GERENTE",
            desconto_maximo_percentual=Decimal("12.00"),
        )

        aprovador = UserModel.objects.create(
            username="gerente_limite12",
            email="gerente12@example.com",
            perfil=perfil_gerente,
        )
       
        terminal = TerminalModel.objects.create(
            filial=filial,
            identificador="CX_DESC_05",
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
            descricao="Produto com limite 5%",
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

        venda = VendaModel.objects.create(
            filial=filial,
            terminal=terminal,
            operador=operador,
            total_bruto=Decimal("100.00"),
            total_desconto=Decimal("0.00"),
            total_liquido=Decimal("100.00"),
        )

        item = VendaItemModel.objects.create(
            venda=venda,
            produto=produto,
            descricao=produto.descricao,
            quantidade=Decimal("1.000"),
            preco_unitario=Decimal("100.000000"),
            total_bruto=Decimal("100.00"),
            percentual_desconto_aplicado=Decimal("0.00"),
            total_liquido=Decimal("100.00"),
        )

        motivo = MotivoDescontoModel.objects.create(
            codigo="DESC20",
            descricao="Tentativa de desconto 20% (acima de todos os limites).",
        )

        logger.info(
            "Tentando aplicar desconto de 20%% (produto=5%%, operador=8%%, aprovador=12%%). "
            "Esperado: desconto proibido."
        )

        with pytest.raises(DescontoNaoPermitidoError) as exc:
            DescontoService.aplicar_desconto_item(
                venda=venda,
                item=item,
                percentual_desconto_aplicado=Decimal("20.00"),
                operador=operador,
                motivo=motivo,
                metodo_pagamento=None,
                aprovador=aprovador,
                aprovador_autenticado=True,
            )

        logger.info(
            "Erro esperado recebido: %s (percentual_solicitado=%s)",
            exc.value.mensagem,
            exc.value.percentual_solicitado,
        )


@pytest.mark.django_db(transaction=True)
def test_prioridade_limite_produto_sobre_filial_e_terminal(two_tenants_with_admins):
    """
    Cenário:
    - Produto: limite 5%.
    - Terminal: limite 15%.
    - Filial: limite 20%.
    - Operador: limite 30%.

    Regra:
    - limite_contexto = PRODUTO (5%), mesmo que terminal/filial sejam maiores.
    - Até 5% -> zona livre.
    - Entre 5% e 30% -> depende do perfil (operador/aprovador).
    """
    schema1 = two_tenants_with_admins["schema1"]

    FilialModel = apps.get_model("filial", "Filial")
    TerminalModel = apps.get_model("terminal", "Terminal")
    ProdutoModel = apps.get_model("produtos", "Produto")
    UserModel = apps.get_model("usuario", "User")
    VendaModel = apps.get_model("vendas", "Venda")
    VendaItemModel = apps.get_model("vendas", "VendaItem")
    MotivoDescontoModel = apps.get_model("promocoes", "MotivoDesconto")

    with schema_context(schema1):
        filial = FilialModel.objects.first()
        operador = UserModel.objects.first()

        perfil = UserPerfil.objects.create(
            descricao="ADMIN",
            desconto_maximo_percentual=Decimal("30.00"),
        )

        operador = UserModel.objects.create(
            username="Operador",
            email="operador@localhost",  
            perfil=perfil,
        )

        filial.desconto_maximo_percentual = Decimal("20.00")
        filial.save(update_fields=["desconto_maximo_percentual"])

        terminal = TerminalModel.objects.create(
            filial=filial,
            identificador="CX_DESC_06",
            ativo=True,
        )
        terminal.desconto_maximo_percentual = Decimal("15.00")
        terminal.save(update_fields=["desconto_maximo_percentual"])

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
            descricao="Produto com limite 5%",
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

        venda = VendaModel.objects.create(
            filial=filial,
            terminal=terminal,
            operador=operador,
            total_bruto=Decimal("100.00"),
            total_desconto=Decimal("0.00"),
            total_liquido=Decimal("100.00"),
        )

        item = VendaItemModel.objects.create(
            venda=venda,
            produto=produto,
            descricao=produto.descricao,
            quantidade=Decimal("1.000"),
            preco_unitario=Decimal("100.000000"),
            total_bruto=Decimal("100.00"),
            percentual_desconto_aplicado=Decimal("0.00"),
            total_liquido=Decimal("100.00"),
        )

        motivo = MotivoDescontoModel.objects.create(
            codigo="DESC5",
            descricao="Desconto 5% na prioridade de produto.",
        )

        logger.info(
            "Aplicando desconto de 5%% (deve cair na zona livre do PRODUTO, "
            "mesmo com terminal=15%%, filial=20%%, operador=30%%)."
        )

        item_atualizado = DescontoService.aplicar_desconto_item(
            venda=venda,
            item=item,
            percentual_desconto_aplicado=Decimal("5.00"),
            operador=operador,
            motivo=motivo,
            metodo_pagamento=None,
            operador_autenticado=False,
        )

        assert item_atualizado.percentual_desconto_aplicado == Decimal("5.00")
        assert item_atualizado.motivo_desconto == motivo

        venda.refresh_from_db()
        assert venda.total_desconto == Decimal("5.00")
        assert venda.total_liquido == Decimal("95.00")

        logger.info(
            "Desconto de 5%% aplicado na zona livre de produto. "
            "total_desconto=%s, total_liquido=%s",
            venda.total_desconto,
            venda.total_liquido,
        )


@pytest.mark.django_db(transaction=True)
def test_zera_desconto_quando_percentual_zero(two_tenants_with_admins):
    """
    Cenário:
    - Item já com desconto aplicado.
    - Chamada de aplicar_desconto_item com percentual_desconto = 0.

    Esperado:
    - Desconto do item é zerado.
    - Motivo e aprovador são limpos.
    - Totais da venda são recalculados.
    """
    schema1 = two_tenants_with_admins["schema1"]

    FilialModel = apps.get_model("filial", "Filial")
    TerminalModel = apps.get_model("terminal", "Terminal")
    ProdutoModel = apps.get_model("produtos", "Produto")
    UserModel = apps.get_model("usuario", "User")
    VendaModel = apps.get_model("vendas", "Venda")
    VendaItemModel = apps.get_model("vendas", "VendaItem")
    MotivoDescontoModel = apps.get_model("promocoes", "MotivoDesconto")

    with schema_context(schema1):
        filial = FilialModel.objects.first()
        operador = UserModel.objects.first()

        terminal = TerminalModel.objects.create(
            filial=filial,
            identificador="CX_DESC_07",
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
            descricao="Produto com desconto inicial",
            preco_venda=Decimal("100.00"),
            grupo=grupo_produto,
            ncm=ncm,
            unidade_comercial_id=unidade.id,
            unidade_tributavel_id=unidade.id,
            ativo=True,
        )

        venda = VendaModel.objects.create(
            filial=filial,
            terminal=terminal,
            operador=operador,
            total_bruto=Decimal("100.00"),
            total_desconto=Decimal("10.00"),
            total_liquido=Decimal("90.00"),
        )

        motivo = MotivoDescontoModel.objects.create(
            codigo="INICIAL",
            descricao="Desconto inicial do item.",
        )

        item = VendaItemModel.objects.create(
            venda=venda,
            produto=produto,
            descricao=produto.descricao,
            quantidade=Decimal("1.000"),
            preco_unitario=Decimal("100.000000"),
            total_bruto=Decimal("100.00"),
            total_liquido=Decimal("90.00"),
            percentual_desconto_aplicado=Decimal("10.00"),
            motivo_desconto=motivo,
        )

        logger.info(
            "Zerando desconto do item (percentual_desconto=0). "
            "Esperado: desconto=0, motivo=None, total_liquido=total_bruto, "
            "venda.total_desconto e total_liquido recalculados."
        )

        item_atualizado = DescontoService.aplicar_desconto_item(
            venda=venda,
            item=item,
            percentual_desconto_aplicado=Decimal("0.00"),
            operador=operador,
            motivo=None,  # não é obrigatório para zerar
            metodo_pagamento=None,
        )

        assert item_atualizado.percentual_desconto_aplicado == Decimal("0.00")
        assert item_atualizado.percentual_desconto_aplicado in (None, Decimal("0.00"))
        assert item_atualizado.motivo_desconto is None
        assert item_atualizado.total_liquido == Decimal("100.00")

        venda.refresh_from_db()
        assert venda.total_desconto in (None, Decimal("0.00"))
        assert venda.total_liquido == Decimal("100.00")

        logger.info(
            "Desconto zerado com sucesso. "
            "venda.total_desconto=%s, venda.total_liquido=%s",
            venda.total_desconto,
            venda.total_liquido,
        )

@pytest.mark.django_db(transaction=True)
def test_aplicar_desconto_total_venda_redistribui_proporcionalmente(two_tenants_with_admins):
    """
    Cenário:
    - Venda com 2 itens:
        * item1: total_bruto = 30,00
        * item2: total_bruto = 70,00
      total_bruto = 100,00
    - Desconto TOTAL de 10,00 aplicado na venda.

    Regras:
    - Desconto permitido pelos limites configurados.
    - Desconto redistribuído proporcionalmente:
        * item1 ≈ 3,00
        * item2 ≈ 7,00
    - Totais da venda atualizados:
        * total_desconto = 10,00
        * total_liquido = 90,00
    """
    schema1 = two_tenants_with_admins["schema1"]

    FilialModel = apps.get_model("filial", "Filial")
    TerminalModel = apps.get_model("terminal", "Terminal")
    ProdutoModel = apps.get_model("produtos", "Produto")
    UserModel = apps.get_model("usuario", "User")
    VendaModel = apps.get_model("vendas", "Venda")
    VendaItemModel = apps.get_model("vendas", "VendaItem")
    MotivoDescontoModel = apps.get_model("promocoes", "MotivoDesconto")

    with schema_context(schema1):
        filial = FilialModel.objects.first()
        assert filial is not None

        perfil = UserPerfil.objects.create(
            descricao="OPERADOR_DESC_TOTAL",
            desconto_maximo_percentual=Decimal("30.00"),
        )

        operador = UserModel.objects.create(
            username="operador_desc_total",
            email="operador_desc_total@localhost",
            perfil=perfil,
        )

        terminal = TerminalModel.objects.create(
            filial=filial,
            identificador="CX_DESC_TOTAL_01",
            ativo=True,
        )
        terminal.desconto_maximo_percentual = Decimal("30.00")
        terminal.save(update_fields=["desconto_maximo_percentual"])

        grupo_produto = GrupoProduto.objects.create(
            descricao="Grupo_desc_total",
            ativo=True,
        )

        ncm = NCM.objects.create(
            descricao="NCM basico",
            codigo="87089990",
            ativo=True,
        )

        unidade = UnidadeMedida.objects.create(
            descricao="Unidade",
            sigla="UN",
            ativo=True,
        )

        produto = ProdutoModel.objects.create(
            descricao="Produto para desconto total",
            preco_venda=Decimal("10.00"),
            grupo=grupo_produto,
            ncm_id=ncm.id,
            unidade_comercial_id=unidade.id,
            unidade_tributavel_id=unidade.id,
            ativo=True,
        )
        # Limite de desconto no produto alto o suficiente para permitir 10%
        if hasattr(produto, "desconto_maximo_percentual"):
            produto.desconto_maximo_percentual = Decimal("20.00")
            produto.save(update_fields=["desconto_maximo_percentual"])

        venda = VendaModel.objects.create(
            filial=filial,
            terminal=terminal,
            operador=operador,
            total_bruto=Decimal("100.00"),
            total_desconto=Decimal("0.00"),
            total_liquido=Decimal("100.00"),
        )

        item1 = VendaItemModel.objects.create(
            venda=venda,
            produto=produto,
            descricao="Item 1",
            quantidade=Decimal("1.000"),
            preco_unitario=Decimal("30.000000"),
            total_bruto=Decimal("30.00"),
            percentual_desconto_aplicado=Decimal("0.00"),
            desconto=Decimal("0.00"),
            total_liquido=Decimal("30.00"),
        )

        item2 = VendaItemModel.objects.create(
            venda=venda,
            produto=produto,
            descricao="Item 2",
            quantidade=Decimal("1.000"),
            preco_unitario=Decimal("70.000000"),
            total_bruto=Decimal("70.00"),
            percentual_desconto_aplicado=Decimal("0.00"),
            desconto=Decimal("0.00"),
            total_liquido=Decimal("70.00"),
        )

        motivo = MotivoDescontoModel.objects.create(
            descricao="Desconto total da venda",
            ativo=True,
        )

        logger.info("Aplicando desconto total de 10,00 na venda.")
        DescontoService.aplicar_desconto_total_venda(
            venda=venda,
            valor_desconto=Decimal("10.00"),
            operador=operador,
            motivo=motivo,
            metodo_pagamento=None,
            aprovador=None,
            operador_autenticado=True,
            aprovador_autenticado=False,
        )

        venda.refresh_from_db()
        item1.refresh_from_db()
        item2.refresh_from_db()

        logger.info(
            "Venda após desconto total: total_bruto=%s, total_desconto=%s, total_liquido=%s",
            venda.total_bruto,
            venda.total_desconto,
            venda.total_liquido,
        )

        assert venda.total_bruto == Decimal("100.00")
        assert venda.total_desconto == Decimal("10.00")
        assert venda.total_liquido == Decimal("90.00")

        desconto_total_itens = item1.desconto + item2.desconto
        assert desconto_total_itens == Decimal("10.00")

        # conferência aproximada da proporção (30/100 e 70/100)
        assert item1.desconto in (Decimal("3.00"), Decimal("2.99"), Decimal("3.01"))
        assert item2.desconto in (Decimal("7.00"), Decimal("6.99"), Decimal("7.01"))