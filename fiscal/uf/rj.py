# fiscal/uf/rj.py
from __future__ import annotations

from .base import CfopDef, NcmDef, FiscalUFConfig


_CFOPS_RJ = {
    "5102": CfopDef(
        codigo="5102",
        descricao="Venda de mercadoria adquirida ou recebida de terceiros",
        aplicacao="Venda interna para consumidor final no RJ.",
    ),
    "5405": CfopDef(
        codigo="5405",
        descricao="Venda de mercadoria adquirida ou recebida de terceiros, sujeita à ST",
        aplicacao="PDV com mercadorias sujeitas à ST no RJ.",
    ),
    "5901": CfopDef(
        codigo="5901",
        descricao="Remessa para demonstração",
        aplicacao="Remessas temporárias.",
    ),
    "5202": CfopDef(
        codigo="5202",
        descricao="Devolução de compra para comercialização",
        aplicacao="Devoluções de compra no RJ.",
    ),
}

_NCMS_RJ = {
    "22029900": NcmDef(
        codigo="22029900",
        descricao="Bebidas não alcoólicas, outras",
        unidade_comercial="UN",
    ),
    "61091000": NcmDef(
        codigo="61091000",
        descricao="Camisetas de algodão",
        unidade_comercial="UN",
    ),
    "64029990": NcmDef(
        codigo="64029990",
        descricao="Calçados, outros",
        unidade_comercial="PAR",
    ),
}


CONFIG = FiscalUFConfig(
    uf="RJ",
    modelo_nfce="65",
    layout_versao="4.00",
    cfops=_CFOPS_RJ,
    ncm=_NCMS_RJ,
    cfop_venda_dentro_uf="5102",
    cfop_venda_fora_uf=None,
    cfop_devolucao="5202",
)
