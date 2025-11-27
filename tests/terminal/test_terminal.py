import pytest
from django.db import transaction, models
from django.db.utils import IntegrityError
from django.apps import apps
from django_tenants.utils import schema_context
from terminal.models import Terminal


# ---------------------------------------------------------------------
# 1. HAPPY PATH – CRIA TERMINAL
# ---------------------------------------------------------------------
@pytest.mark.django_db(transaction=True)
def test_criar_terminal_sucesso(two_tenants_with_admins):
    schema1 = two_tenants_with_admins["schema1"]
    FilialModel = apps.get_model("filial", "Filial")

    with schema_context(schema1):
        filial = FilialModel.objects.first()
        assert filial is not None

        terminal = Terminal.objects.create(
            filial=filial,
            identificador="PDV-01",
            permite_suprimento=True,
            permite_sangria=True,
            ativo=True
        )

        assert terminal.filial == filial
        assert terminal.identificador == "PDV-01"
        assert terminal.ativo is True
        assert terminal.permite_sangria is True

        # __str__ test
        assert str(terminal) == f"{filial.nome_fantasia} - PDV-01"


# ---------------------------------------------------------------------
# 2. UNIQUE IDENTIFIER PER FILIAL
# ---------------------------------------------------------------------
@pytest.mark.django_db(transaction=True)
def test_unicidade_identificador_por_filial(two_tenants_with_admins):
    schema1 = two_tenants_with_admins["schema1"]
    FilialModel = apps.get_model("filial", "Filial")

    with schema_context(schema1):
        filial = FilialModel.objects.first()
        assert filial is not None

        # Cria o primeiro terminal
        Terminal.objects.create(filial=filial, identificador="CAIXA-01")

        # Segundo com o mesmo identificador deve falhar
        with transaction.atomic(), pytest.raises(IntegrityError):
            Terminal.objects.create(filial=filial, identificador="CAIXA-01")

        # Identificador diferente deve funcionar
        t2 = Terminal.objects.create(filial=filial, identificador="CAIXA-02")
        assert t2.pk is not None


# ---------------------------------------------------------------------
# 3. IDENTIFICADOR REPETIDO EM FILIAIS DIFERENTES
# ---------------------------------------------------------------------
@pytest.mark.django_db(transaction=True)
def test_identificador_repetido_em_filiais_diferentes(two_tenants_with_admins):
    """
    Duas filiais do mesmo tenant podem ter o mesmo identificador de terminal.
    """
    schema1 = two_tenants_with_admins["schema1"]
    FilialModel = apps.get_model("filial", "Filial")
    EnderecoModel = apps.get_model("enderecos", "Endereco")

    with schema_context(schema1):
        # Filial 1 criada automaticamente pelo endpoint
        filial1 = FilialModel.objects.first()
        assert filial1 is not None

        Terminal.objects.create(filial=filial1, identificador="PDV-01")

        # Criar endereço para Filial 2
        endereco2 = EnderecoModel.objects.create(
            logradouro=filial1.endereco.logradouro,
            numero="200",
            complemento="",
            referencia="",
            cep=filial1.endereco.cep,
        )

        # Criar Filial 2 manualmente
        filial2 = FilialModel.objects.create(
            razao_social="Filial 2 Ltda",
            nome_fantasia="Loja Filial 2",
            cnpj="22222222000200",
            endereco=endereco2,
            ativo=True
        )

        assert filial2.pk != filial1.pk

        # Criar terminal com mesmo identificador na Filial 2 → deve funcionar
        terminal_f2 = Terminal.objects.create(
            filial=filial2,
            identificador="PDV-01",
        )

        assert terminal_f2.pk is not None
        assert terminal_f2.filial != filial1




# ---------------------------------------------------------------------
# 4. DELETE PROTECTION
# ---------------------------------------------------------------------
@pytest.mark.django_db(transaction=True)
def test_protecao_delecao_filial(two_tenants_with_admins):
    schema1 = two_tenants_with_admins["schema1"]
    FilialModel = apps.get_model("filial", "Filial")

    with schema_context(schema1):
        filial = FilialModel.objects.first()
        assert filial is not None

        Terminal.objects.create(filial=filial, identificador="SAT-01")

        # PROTECT deve impedir deleção
        with pytest.raises(models.ProtectedError):
            filial.delete()


# ---------------------------------------------------------------------
# 5. FILTRO TERMINAIS ATIVOS
# ---------------------------------------------------------------------
@pytest.mark.django_db(transaction=True)
def test_filtro_terminais_ativos(two_tenants_with_admins):
    schema1 = two_tenants_with_admins["schema1"]
    FilialModel = apps.get_model("filial", "Filial")

    with schema_context(schema1):
        filial = FilialModel.objects.first()
        assert filial is not None

        t_ativo = Terminal.objects.create(
            filial=filial,
            identificador="T-ATIVO",
            ativo=True
        )

        t_inativo = Terminal.objects.create(
            filial=filial,
            identificador="T-INATIVO",
            ativo=False
        )

        ativos = Terminal.objects.filter(ativo=True)

        assert t_ativo in ativos
        assert t_inativo not in ativos
        assert ativos.count() == 1
