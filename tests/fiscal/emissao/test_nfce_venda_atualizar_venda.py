import logging
import uuid
import pytest
from decimal import Decimal
from django.apps import apps
from django_tenants.utils import schema_context

from fiscal.services.nfce_venda_service import atualizar_venda_apos_emissao_nfce
from usuario.models.usuario_models import User, UserFilial, UserPerfil
from vendas.models.venda_models import VendaStatus

logger = logging.getLogger(__name__)

pytestmark = pytest.mark.django_db(transaction=True)


# -----------------------------------------------------------------------------------
# Helpers corrigidos para receber APENAS schema_name (string)
# igual ao teste idempotente que funciona.
# -----------------------------------------------------------------------------------
def _criar_filial_terminal_e_venda(schema_name: str):
    Filial = apps.get_model("filial", "Filial")
    Terminal = apps.get_model("terminal", "Terminal")
    Venda = apps.get_model("vendas", "Venda")

    with schema_context(schema_name):
        filial = Filial.objects.first()
        assert filial is not None, "Nenhuma Filial foi criada pelo tenant API!"
        print("DEBUG: Filial encontrada:", filial)
        terminal = Terminal.objects.create(
            identificador="T001",
            filial=filial,
            ativo=True,
            #numero_atual_nfce=1,
        )
        perfil = UserPerfil.objects.create(
            descricao="Perfil de Teste",
            desconto_maximo_percentual=Decimal("10.00"),
        )

        operador = User.objects.create(
            username="OperadorTeste",
            email="vinculo_unico_t1@example.com",
            perfil=perfil,
            is_active=True,
        )

        # Primeiro vínculo OK
        UserFilial.objects.create(
            user=operador,
            filial_id=filial.id,
        )
        print("DEBUG: Terminal criado:", terminal)
        venda = Venda.objects.create(
            filial=filial,
            terminal=terminal,
            operador=operador,
            status=VendaStatus.AGUARDANDO_EMISSAO_FISCAL,
            documento_fiscal_tipo="NFC_E",
            total_bruto=Decimal("100.00"),
            total_desconto=Decimal("0.00"),
            total_liquido=Decimal("100.00"),
            total_pago=Decimal("100.00"),
            total_troco=Decimal("0.00"),
        )
        print("DEBUG: Venda criada:", venda)
    return filial, terminal, venda



def _criar_nfce_documento(
    schema_name: str,
    filial,
    terminal,
    status: str,
    em_contingencia: bool = False,
    raw_sefaz: dict | None = None,
    mensagem: str | None = None,
):
    print("DEBUG: Iniciando criação de NfceDocumento com status:", status)
    NfceDocumento = apps.get_model("fiscal", "NfceDocumento")
    print("DEBUG: Criando NfceDocumento com status:", status)
    with schema_context(schema_name):
        return NfceDocumento.objects.create(
            filial=filial,
            terminal=terminal,
            numero=1,
            serie=1,
            status=status,
            request_id=uuid.uuid4(),
            chave_acesso="12345678901234567890123456789012345678901234",
            protocolo="",
            xml_autorizado=None,
            ambiente="HOMOLOGACAO",
            uf=getattr(filial, "uf", "SP"),
            em_contingencia=em_contingencia,
            mensagem_sefaz=mensagem or "",
            raw_sefaz_response=raw_sefaz or {},
        )

    print("DEBUG: NfceDocumento criado:", NfceDocumento)
# -----------------------------------------------------------------------------------
# Testes corrigidos
# -----------------------------------------------------------------------------------
def test_atualizar_venda_quando_nfce_autorizada(two_tenants_with_admins):
    schema1 = two_tenants_with_admins["schema1"]

    logger.info(
        "Iniciando teste: atualizar_venda_apos_emissao_nfce com documento autorizado (schema=%s).",
        schema1,
    )
    
    filial, terminal, venda = _criar_filial_terminal_e_venda(schema1)
    print("DEBUG: Filial, Terminal e Venda criados:", filial, terminal, venda)
    doc = _criar_nfce_documento(
        schema1,
        filial=filial,
        terminal=terminal,
        status="autorizada",
        raw_sefaz={"codigo": "100", "mensagem": "Autorizado o uso da NF-e"},
    )

    print("DEBUG: Documento NFCE criado:", doc)

    with schema_context(schema1):
        venda_atualizada = atualizar_venda_apos_emissao_nfce(
            venda=venda,
            documento=doc,
        )
    print("DEBUG: Venda atualizada:", venda_atualizada)
    assert venda_atualizada.status == "FINALIZADA"
    assert venda_atualizada.nfce_documento_id == doc.id
    assert venda_atualizada.codigo_erro_fiscal is None
    assert venda_atualizada.mensagem_erro_fiscal is None


def test_atualizar_venda_quando_nfce_rejeitada(two_tenants_with_admins):
    schema1 = two_tenants_with_admins["schema1"]

    logger.info(
        "Iniciando teste: atualizar_venda_apos_emissao_nfce com documento rejeitado (schema=%s).",
        schema1,
    )

    filial, terminal, venda = _criar_filial_terminal_e_venda(schema1)

    doc = _criar_nfce_documento(
        schema1,
        filial=filial,
        terminal=terminal,
        status="rejeitada",
        raw_sefaz={"codigo": "215", "mensagem": "Rejeição: Falha no schema XML"},
        mensagem="Rejeição: Falha no schema XML",
    )

    with schema_context(schema1):
        venda_atualizada = atualizar_venda_apos_emissao_nfce(
            venda=venda,
            documento=doc,
        )

    assert venda_atualizada.status == "ERRO_FISCAL"
    assert venda_atualizada.nfce_documento_id == doc.id
    assert venda_atualizada.codigo_erro_fiscal in ("215", "215.0", None)
    assert "Rejeição" in (venda_atualizada.mensagem_erro_fiscal or "")


def test_atualizar_venda_quando_nfce_em_contingencia(two_tenants_with_admins):
    schema1 = two_tenants_with_admins["schema1"]

    logger.info(
        "Iniciando teste: atualizar_venda_apos_emissao_nfce com contingência (schema=%s).",
        schema1,
    )

    filial, terminal, venda = _criar_filial_terminal_e_venda(schema1)

    doc = _criar_nfce_documento(
        schema1,
        filial=filial,
        terminal=terminal,
        status="contingencia_pendente",
        em_contingencia=True,
        raw_sefaz={},
        mensagem="Erro técnico na comunicação com a SEFAZ",
    )

    with schema_context(schema1):
        venda_atualizada = atualizar_venda_apos_emissao_nfce(
            venda=venda,
            documento=doc,
        )

    assert venda_atualizada.status == "ERRO_FISCAL"
    assert venda_atualizada.nfce_documento_id == doc.id
    assert venda_atualizada.mensagem_erro_fiscal
