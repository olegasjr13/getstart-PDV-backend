from decimal import Decimal
from filial.models.filial_models import Filial
from terminal.models.terminal_models import Terminal
from usuario.models.usuario_models import User
from vendas.models.venda_models import TipoDocumentoFiscal, TipoVenda, Venda, VendaStatus
from vendas.services.vendas.abrir_venda_services import abrir_venda
from django.db import transaction
import logging

logger = logging.getLogger(__name__)
@transaction.atomic
def abrir_orcamento(
    *,
    filial: Filial,
    terminal: Terminal,
    operador: User,
    request_id: str | None = None,
    observacoes: str | None = None,
) -> Venda:
    """
    Abre um ORÇAMENTO (sem documento fiscal) para a filial/terminal informados.
    """
    logger.info(
        "Abrindo orçamento: filial_id=%s terminal_id=%s operador_id=%s request_id=%s",
        filial.id,
        terminal.id,
        operador.id,
        request_id,
    )

    venda = Venda(
        filial=filial,
        terminal=terminal,
        operador=operador,
        tipo_venda=TipoVenda.ORCAMENTO,
        documento_fiscal_tipo=TipoDocumentoFiscal.NENHUM,
        status=VendaStatus.ABERTA,
        total_bruto=Decimal("0.00"),
        total_desconto=Decimal("0.00"),
        total_liquido=Decimal("0.00"),
        total_pago=Decimal("0.00"),
        total_troco=Decimal("0.00"),
        request_id=request_id,
        observacoes=observacoes,
    )

    venda.clean()
    venda.save()

    logger.info("Orçamento aberto com sucesso. venda_id=%s", venda.id)
    return venda

