from uuid import uuid4

from django.forms import ValidationError
import pytest
from vendas.models.venda_models import TipoDocumentoFiscal, TipoVenda
from vendas.services.vendas.abrir_venda_services import abrir_venda


@pytest.mark.django_db
def test_abrir_venda_sem_caixa_aberto_dispara_erro(
    filial_factory,
    terminal_factory,
    usuario_factory,
):
    filial = filial_factory()
    terminal = terminal_factory(filial=filial, abre_fecha_caixa=True)
    operador = usuario_factory()

    request_id = uuid4()

    with pytest.raises(ValidationError):
        abrir_venda(
            filial=filial,
            terminal=terminal,
            operador=operador,
            tipo_venda=TipoVenda.VENDA_BALCAO,
            tipo_documento_fiscal=TipoDocumentoFiscal.NFCE,
            request_id=request_id,
        )
