# fiscal/uf/sp.py
from __future__ import annotations

from .base import CfopDef, NcmDef, FiscalUFConfig


# --------------------------------------------------------------------
# CFOPs base para SP (varejo / PDV)
# --------------------------------------------------------------------
_CFOPS_SP = {
    # Venda mercadoria adquirida de terceiros – dentro do estado
    "5102": CfopDef(
        codigo="5102",
        descricao="Venda de mercadoria adquirida ou recebida de terceiros",
        aplicacao="Venda interna para consumidor final (mercadoria de revenda).",
    ),
    # Venda com ST – comum em varejo com produtos sujeitos à ST
    "5405": CfopDef(
        codigo="5405",
        descricao="Venda de mercadoria adquirida ou recebida de terceiros, sujeita à ST",
        aplicacao="PDV com mercadorias sujeitas à substituição tributária.",
    ),
    # Remessa não definitiva (demonstração, etc.)
    "5901": CfopDef(
        codigo="5901",
        descricao="Remessa para demonstração",
        aplicacao="Remessas temporárias sem transferência de propriedade.",
    ),
    # Devolução de compra
    "5202": CfopDef(
        codigo="5202",
        descricao="Devolução de compra para comercialização",
        aplicacao="Usado em devoluções de compras de mercadorias de revenda.",
    ),
}

# --------------------------------------------------------------------
# NCMs base para SP (exemplos reais e úteis em PDV)
# --------------------------------------------------------------------
_NCMS_SP = {
    "22029900": NcmDef(
        codigo="22029900",
        descricao="Bebidas não alcoólicas, outras",
        unidade_comercial="UN",
        cest=None,
    ),
    "61091000": NcmDef(
        codigo="61091000",
        descricao="Camisetas de algodão",
        unidade_comercial="UN",
        cest=None,
    ),
    "64029990": NcmDef(
        codigo="64029990",
        descricao="Calçados, outros",
        unidade_comercial="PAR",
        cest=None,
    ),
}


CONFIG = FiscalUFConfig(
    uf="SP",
    modelo_nfce="65",
    layout_versao="4.00",
    cfops=_CFOPS_SP,
    ncm=_NCMS_SP,
    # defaults operacionais para o PDV em SP
    cfop_venda_dentro_uf="5102",
    cfop_venda_fora_uf=None,  # NFC-e geralmente uso interno, mas podemos evoluir
    cfop_devolucao="5202",
)
