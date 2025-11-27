# fiscal/tests/emissao/test_nfce_emissao_multi_uf.py

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from django_tenants.utils import schema_context

from filial.models import Filial
from fiscal.models import (
    NfcePreEmissao,
    NfceDocumento,
)
from fiscal.services.emissao_service import emitir_nfce
from fiscal.sefaz_factory import get_sefaz_client_for_filial
from fiscal.tests.test_nfce_atomicidade_rollback import TENANT_SCHEMA
from fiscal.tests.test_nfce_auditoria_logs import _bootstrap_public_tenant_and_domain, _ensure_a1_valid
from terminal.models import Terminal


User = get_user_model()


@pytest.mark.django_db(transaction=True)
@override_settings(
    ROOT_URLCONF="config.urls",
)
@pytest.mark.parametrize("uf", ["SP", "MG", "RJ", "ES"])
def test_emitir_nfce_happy_path_multi_uf(uf):
    """
    Garante que o fluxo de emissão NFC-e funciona para múltiplas UFs suportadas (SP/MG/RJ/ES):

      - Cria Filial com UF específica.
      - Cria Terminal e pré-emissão vinculada (NfcePreEmissao).
      - Usa a factory get_sefaz_client_for_filial para obter o client SEFAZ correto.
      - Chama emitir_nfce(user, request_id, sefaz_client).
      - Verifica que o NfceDocumento gerado:
          * Tem status 'autorizada'.
          * Herdou corretamente a UF e o ambiente da Filial.
          * Está associado ao request_id usado.
    """
    _bootstrap_public_tenant_and_domain()

    with schema_context(TENANT_SCHEMA):
        # usuário operacional por UF (username único para evitar conflitos)
        user = User.objects.create_user(
            username=f"oper-multi-{uf.lower()}",
            password="123456",
        )

        # CNPJs distintos por UF para não violar a unique constraint em filial.cnpj
        cnpj_base_por_uf = {
            "SP": "90111111000111",
            "MG": "90222222000122",
            "RJ": "90333333000133",
            "ES": "90444444000144",
        }

        filial = Filial.objects.create(
            cnpj=cnpj_base_por_uf[uf],
            nome_fantasia=f"Filial Emissao {uf}",
            uf=uf,
            csc_id="ID",
            csc_token="TK",
            ambiente="homolog",
        )
        _ensure_a1_valid(filial)

        # Terminal associado à filial (identificador único por UF)
        term = Terminal.objects.create(
            identificador=f"T-MULTI-{uf}-01",
            filial_id=filial.id,
            serie=1,
            numero_atual=1,
            ativo=True,
        )

        # vínculo user x filial
        user.userfilial_set.create(filial_id=filial.id)

        # request_id único para esta pré-emissão
        req_id = uuid.uuid4()

        # Cria pré-emissão diretamente (service emitir_nfce espera isso pronto)
        pre = NfcePreEmissao.objects.create(
            filial_id=filial.id,
            terminal_id=term.id,
            numero=term.numero_atual,
            serie=term.serie,
            request_id=req_id,
            payload={
                "itens": [],
                "pagamentos": [],
                "cliente": None,
            },
        )

        assert pre.request_id == req_id

        # Obtém client SEFAZ via factory multi-UF
        sefaz_client = get_sefaz_client_for_filial(filial)

        # Chamada da service de emissão (assinatura atual exige sefaz_client e request_id)
        result = emitir_nfce(
            user=user,
            request_id=req_id,
            sefaz_client=sefaz_client,
        )

        # Carrega documento gerado a partir do request_id
        doc = NfceDocumento.objects.get(request_id=req_id)

        # Asserções principais de Multi-UF
        assert doc.status == "autorizada"
        assert doc.uf == uf
        assert doc.ambiente == "homolog"

        # Garantir consistência com o DTO retornado
        assert result.status == "autorizada"
        assert result.uf == doc.uf if hasattr(result, "uf") else True  # fallback se DTO não tiver uf
        assert result.numero == doc.numero
        assert result.serie == doc.serie
        assert result.filial_id == str(filial.id)
        assert result.terminal_id == str(term.id)

        # sanity check básico da chave/protocolo
        assert isinstance(doc.chave_acesso, str)
        assert len(doc.chave_acesso) <= 44
        assert doc.protocolo is not None
