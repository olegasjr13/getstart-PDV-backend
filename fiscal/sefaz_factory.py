# fiscal/sefaz_factory.py
"""
Factory de clients SEFAZ por UF / ambiente.

Objetivos:
- Isolar a escolha do client SEFAZ (mock ou real) em um único ponto.
- Suportar múltiplas UFs (SP, MG, RJ, ES) e ambientes (homolog, producao).
- Facilitar a evolução futura para clients reais por UF (SPClient, MGClient, etc).

No momento, todos os ambientes/UFs usam MockSefazClient por padrão,
e MockSefazClientAlwaysFail para cenários de falha técnica / contingência
(simulações em testes).
"""

from __future__ import annotations

from typing import Type

from filial.models import Filial  # modelo de filial do projeto
from fiscal.sefaz_clients import (
    MockSefazClient,
    MockSefazClientAlwaysFail,
    SefazClientProtocol,
)


# UFs oficialmente suportadas neste MVP
SUPPORTED_UFS = {"SP", "MG", "RJ", "ES"}

# Mapeamento de UF -> classe de client.
# Por enquanto, todas usam MockSefazClient, mas este dicionário
# permite, no futuro, plugar implementações reais específicas por UF.
CLIENT_CLASS_BY_UF: dict[str, Type[SefazClientProtocol]] = {
    "SP": MockSefazClient,
    "MG": MockSefazClient,
    "RJ": MockSefazClient,
    "ES": MockSefazClient,
}


def _normalize_ambiente(ambiente: str | None) -> str:
    """
    Normaliza o valor de ambiente vindo da Filial.

    Aceitamos variações comuns e convertemos para:
      - "homolog"
      - "producao"
    """
    if not ambiente:
        return "homolog"

    amb = ambiente.strip().lower()
    if amb in {"homolog", "homologacao", "teste"}:
        return "homolog"
    if amb in {"prod", "producao", "produção"}:
        return "producao"

    # fallback conservador
    return amb


def _normalize_uf(uf: str | None) -> str:
    """
    Normaliza a UF para duas letras maiúsculas.
    """
    if not uf:
        return "SP"
    return uf.strip().upper()


def get_sefaz_client_for_filial(
    filial: Filial,
    *,
    force_technical_fail: bool = False,
) -> SefazClientProtocol:
    """
    Retorna uma instância de client SEFAZ apropriada para a filial informada.

    Regras atuais:
      - Ambiente é derivado de filial.ambiente, normalizado.
      - UF é derivada de filial.uf, normalizada.
      - Para SP/MG/RJ/ES, usamos MockSefazClient (MVP multi-UF).
      - force_technical_fail=True força uso de MockSefazClientAlwaysFail
        (usado em testes de contingência).

    Este é o ponto único onde, futuramente, vamos plugar implementações
    reais por UF, sem precisar alterar services/views.
    """
    uf = _normalize_uf(getattr(filial, "uf", None))
    ambiente = _normalize_ambiente(getattr(filial, "ambiente", None))

    if force_technical_fail:
        return MockSefazClientAlwaysFail(ambiente=ambiente, uf=uf)

    client_cls: Type[SefazClientProtocol]

    if uf in CLIENT_CLASS_BY_UF:
        client_cls = CLIENT_CLASS_BY_UF[uf]
    else:
        # Fallback para UFs não mapeadas explicitamente – mantém comportamento
        # previsível mesmo se algum dado vier errado do banco.
        client_cls = MockSefazClient

    return client_cls(ambiente=ambiente, uf=uf)
