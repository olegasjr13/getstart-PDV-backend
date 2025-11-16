# fiscal/sefaz_factory.py

"""
Factory para criação de clients SEFAZ.

Por enquanto, todos os caminhos retornam MockSefazClient, mas a estrutura
já está preparada para, no futuro, ter implementations reais por UF/ambiente:
  - SP homolog / produção
  - MG homolog / produção
  - RJ homolog / produção
  - ES homolog / produção
"""

from __future__ import annotations

from typing import Literal

from filial.models.filial_models import Filial

from .sefaz_clients import MockSefazClient, SefazClientProtocol


UFType = Literal["SP", "MG", "RJ", "ES"]


def _normalizar_ambiente(ambiente: str) -> str:
    """
    Normaliza o valor de ambiente configurado na Filial para
    algo consistente ('homolog' ou 'producao').
    """
    if not ambiente:
        return "homolog"

    ambiente = ambiente.lower()

    if ambiente.startswith("homolog"):
        return "homolog"

    if ambiente.startswith("prod"):
        return "producao"

    # fallback seguro
    return "homolog"


def get_sefaz_client_for_filial(filial: Filial) -> SefazClientProtocol:
    """
    Retorna o client SEFAZ apropriado para a filial informada.

    Regras atuais (MVP):
      - Suportamos UF: SP, MG, RJ, ES.
      - Ambientes: homolog / producao (normalizados).
      - Neste momento, SEMPRE retornamos MockSefazClient,
        mas a estrutura de decisão já está montada.
    """

    uf = (filial.uf or "").upper()
    ambiente_norm = _normalizar_ambiente(getattr(filial, "ambiente", "") or "")

    # Validação mínima de UF
    if uf not in {"SP", "MG", "RJ", "ES"}:
        # Mantemos MockSefazClient como fallback para UFs não mapeadas.
        # Quando forem implementados clients reais, aqui podemos levantar
        # um erro mais explícito ou logar um aviso.
        return MockSefazClient(ambiente=ambiente_norm, uf=uf or "SP")

    # Ponto de decisão futuro:
    # Exemplo de como poderia ser:
    #
    # if uf == "SP" and ambiente_norm == "homolog":
    #     return SefazSpHomologClient(...)
    # if uf == "SP" and ambiente_norm == "producao":
    #     return SefazSpProducaoClient(...)
    # if uf == "MG" and ambiente_norm == "homolog":
    #     ...
    #
    # Por enquanto, usamos MockSefazClient para todos os casos.
    return MockSefazClient(ambiente=ambiente_norm, uf=uf)
