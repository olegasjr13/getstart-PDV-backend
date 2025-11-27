from django.forms import ValidationError
from vendas.models.venda_models import TipoDocumentoFiscal, TipoVenda, Venda, VendaStatus

from django.db import transaction
import logging

logger = logging.getLogger(__name__)

@transaction.atomic
def converter_orcamento_em_venda(
    *,
    venda: Venda,
    documento_fiscal_tipo: str = TipoDocumentoFiscal.NFCE,
) -> Venda:
    """
    Converte um ORÇAMENTO em VENDA_NORMAL, preparando para emissão fiscal.

    - Garante que a venda é ORÇAMENTO.
    - Garante que ainda não há documento fiscal associado.
    - Mantém itens e totais.
    """
    if venda.tipo_venda != TipoVenda.ORCAMENTO:
        raise ValueError("A venda informada não é um ORÇAMENTO.")

    if venda.documento_fiscal_tipo != TipoDocumentoFiscal.NENHUM:
        raise ValidationError(
            {
                "documento_fiscal_tipo": (
                    "Não é possível converter orçamento que já possui "
                    "tipo de documento fiscal configurado."
                )
            }
        )

    venda.tipo_venda = TipoVenda.VENDA_NORMAL
    venda.documento_fiscal_tipo = documento_fiscal_tipo
    venda.status = VendaStatus.ABERTA

    venda.clean()
    venda.save(
        update_fields=["tipo_venda", "documento_fiscal_tipo", "status"]
    )

    logger.info(
        "Orçamento convertido em venda normal. venda_id=%s tipo_doc=%s",
        venda.id,
        venda.documento_fiscal_tipo,
    )

    return venda
