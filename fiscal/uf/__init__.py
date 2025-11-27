# fiscal/uf/__init__.py
from __future__ import annotations

from typing import Dict

from .base import FiscalUFConfig
from . import sp, mg, rj, es


# Registry interno, 1:1 por UF
_UF_CONFIGS: Dict[str, FiscalUFConfig] = {
    sp.CONFIG.uf: sp.CONFIG,
    mg.CONFIG.uf: mg.CONFIG,
    rj.CONFIG.uf: rj.CONFIG,
    es.CONFIG.uf: es.CONFIG,
}


def get_uf_config(uf: str | None) -> FiscalUFConfig:
    """
    Retorna a configuração fiscal para a UF informada.

    Regras:
      - Normaliza UF para maiúsculas.
      - Se vier None ou string vazia, assume 'SP' como default.
      - Se UF não estiver mapeada explicitamente, também faz fallback para 'SP'.

    Isso garante que mudanças em uma UF fiquem isoladas nos arquivos
    respectivos (sp.py, mg.py, rj.py, es.py).
    """
    if not uf:
        return _UF_CONFIGS["SP"]

    key = uf.strip().upper()
    return _UF_CONFIGS.get(key, _UF_CONFIGS["SP"])
