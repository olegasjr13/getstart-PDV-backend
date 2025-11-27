# fiscal/uf/base.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional


@dataclass(frozen=True)
class CfopDef:
    """
    Definição de um CFOP utilizado no PDV.

    - codigo: CFOP em formato '5102', '5405', etc.
    - descricao: descrição oficial/resumida.
    - aplicacao: como esse CFOP é usado no contexto do PDV (venda consumidor, devolução, etc).
    """
    codigo: str
    descricao: str
    aplicacao: str


@dataclass(frozen=True)
class NcmDef:
    """
    Definição de um NCM utilizado no catálogo de produtos.

    - codigo: NCM em formato '22029900', etc.
    - descricao: descrição resumida.
    - unidade_comercial: unidade padrão (UN, CX, KG, PAR, etc).
    - cest: opcional, usado quando necessário (produtos sujeitos a ST).
    """
    codigo: str
    descricao: str
    unidade_comercial: str
    cest: Optional[str] = None


@dataclass(frozen=True)
class FiscalUFConfig:
    """
    Configuração fiscal base por UF, utilizada por:

      - Emissão NFC-e (modelo, layout, CFOP padrão de venda).
      - Cancelamento (apenas leitura de UF/ambiente).
      - Inutilização (UF + faixa numérica).
      - Seeds de CFOP/NCM (massa fiscal mínima realista).

    Essa config não fala com a SEFAZ diretamente; ela só organiza
    metadados fiscais usados pelos services.
    """

    # Identificação
    uf: str  # 'SP', 'MG', 'RJ', 'ES'
    modelo_nfce: str  # normalmente '65'
    layout_versao: str  # '4.00' para NFC-e layout 4.00

    # Catálogo fiscal por UF
    cfops: Mapping[str, CfopDef]
    ncm: Mapping[str, NcmDef]

    # Defaults operacionais
    cfop_venda_dentro_uf: str
    cfop_venda_fora_uf: Optional[str] = None
    cfop_devolucao: Optional[str] = None
