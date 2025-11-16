"""
Camada de client SEFAZ.

Este módulo define:

- Contratos para comunicação com a SEFAZ.
- Implementação MockSefazClient, usada em ambiente de desenvolvimento/teste.
- Implementação MockSefazClientAlwaysFail, usada em testes de contingência.
- Estrutura pronta para, no futuro, termos clients reais por UF/ambiente
  (SP, MG, RJ, ES, homologação/produção).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Dict, Protocol, Optional


# ---------------------------------------------------------------------------
# Exceções específicas
# ---------------------------------------------------------------------------


class SefazTechnicalError(Exception):
    """
    Erros técnicos na comunicação com a SEFAZ (timeout, conexão, erro interno).

    Essa exceção é usada para distinguir problemas de infraestrutura/integração
    (onde ativamos contingência) de rejeições fiscais normais (código 4xx/5xx
    de regras de negócio, que não ativam contingência).
    """

    def __init__(
        self,
        message: str,
        *,
        codigo: str | None = None,
        raw: Dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.codigo = codigo
        self.raw: Dict[str, Any] = raw or {}


# ---------------------------------------------------------------------------
# DTOs de resposta da SEFAZ
# ---------------------------------------------------------------------------


@dataclass
class SefazAutorizacaoResponse:
    """
    Resultado de uma tentativa de autorização de NFC-e.

    Este DTO é pensado para ser facilmente mapeado para:
      - NfceDocumento
      - NfceAuditoria
    """

    codigo: int
    mensagem: str
    protocolo: str
    chave_acesso: str
    xml_autorizado: Optional[str]
    raw: Dict[str, Any]


@dataclass
class SefazCancelamentoResponse:
    """
    Resultado de um evento de cancelamento de NFC-e.
    """

    codigo: int
    mensagem: str
    protocolo: str
    raw: Dict[str, Any]


@dataclass
class SefazInutilizacaoResponse:
    """
    Resultado de uma inutilização de faixa numérica de NFC-e.
    """

    codigo: int
    mensagem: str
    protocolo: str
    raw: Dict[str, Any]


# ---------------------------------------------------------------------------
# Contrato do client SEFAZ
# ---------------------------------------------------------------------------


class SefazClientProtocol(Protocol):
    """
    Contrato mínimo que um client SEFAZ deve cumprir.

    As services de emissão/cancelamento/inutilização dependem deste protocolo,
    e não da implementação concreta.
    """

    def autorizar_nfce(
        self,
        *,
        filial,
        pre_emissao,
        numero: int,
        serie: int,
    ) -> SefazAutorizacaoResponse:
        ...

    def cancelar_nfce(
        self,
        *,
        filial,
        documento,
        motivo: str,
    ) -> SefazCancelamentoResponse:
        ...

    def inutilizar_faixa(
        self,
        *,
        filial,
        serie: int,
        numero_inicial: int,
        numero_final: int,
        motivo: str,
    ) -> SefazInutilizacaoResponse:
        ...


# ---------------------------------------------------------------------------
# Implementação mock de client SEFAZ
# ---------------------------------------------------------------------------


class MockSefazClient(SefazClientProtocol):
    """
    Implementação mock de client SEFAZ.

    Usada em desenvolvimento e testes, simulando respostas bem-sucedidas
    da SEFAZ, com dados coerentes o suficiente para alimentar as models
    e os DTOs internos.

    Observações:
      - A chave de acesso é gerada com no máximo 44 caracteres,
        para respeitar a constraint de NfceDocumento.
      - Os códigos de retorno seguem convenções comuns:
          * 100/150 para autorização
          * 135 para cancelamento
          * 102 para inutilização
        (mas estes valores podem ser ajustados caso você queira
        simuladores mais fiéis por UF).
    """

    def __init__(self, *, ambiente: str = "homolog", uf: Optional[str] = None):
        self.ambiente = ambiente
        self.uf = uf or "SP"

    # -------------------------
    # Autorização NFC-e
    # -------------------------
    def autorizar_nfce(
        self,
        *,
        filial,
        pre_emissao,
        numero: int,
        serie: int,
    ) -> SefazAutorizacaoResponse:
        # Gera uma chave de acesso mock coerente com o tamanho máximo (44)
        # Exemplo: "NFe" + 41 caracteres → total 44
        random_suffix = uuid.uuid4().hex[:41]  # 41 chars
        chave_acesso = "NFe" + random_suffix  # 3 + 41 = 44

        protocolo = f"PROTO-{uuid.uuid4().hex[:10]}"

        mensagem = "Autorizado o uso da NFC-e (mock)."

        raw = {
            "codigo": 100,
            "mensagem": mensagem,
            "protocolo": protocolo,
            "chave_acesso": chave_acesso,
            "ambiente": self.ambiente,
            "uf": self.uf,
        }

        xml = (
            f"<xml-autorizado numero='{numero}' "
            f"serie='{serie}' chave='{chave_acesso}' />"
        )

        return SefazAutorizacaoResponse(
            codigo=100,
            mensagem=mensagem,
            protocolo=protocolo,
            chave_acesso=chave_acesso,
            xml_autorizado=xml,
            raw=raw,
        )

    # -------------------------
    # Cancelamento NFC-e
    # -------------------------
    def cancelar_nfce(
        self,
        *,
        filial,
        documento,
        motivo: str,
    ) -> SefazCancelamentoResponse:
        protocolo = f"CANCEL-{documento.chave_acesso[-10:]}"
        mensagem = "Cancelamento homologado (mock)."

        raw = {
            "codigo": 135,
            "mensagem": mensagem,
            "protocolo": protocolo,
            "motivo": motivo,
            "ambiente": self.ambiente,
            "uf": self.uf,
        }

        return SefazCancelamentoResponse(
            codigo=135,
            mensagem=mensagem,
            protocolo=protocolo,
            raw=raw,
        )

    # -------------------------
    # Inutilização de faixa
    # -------------------------
    def inutilizar_faixa(
        self,
        *,
        filial,
        serie: int,
        numero_inicial: int,
        numero_final: int,
        motivo: str,
    ) -> SefazInutilizacaoResponse:
        faixa = f"{numero_inicial}-{numero_final}"
        protocolo = f"INUT-{self.uf}-{serie}-{faixa}"
        mensagem = "Inutilização de faixa homologada (mock)."

        raw = {
            "codigo": 102,
            "mensagem": mensagem,
            "protocolo": protocolo,
            "faixa": faixa,
            "motivo": motivo,
            "ambiente": self.ambiente,
            "uf": self.uf,
        }

        return SefazInutilizacaoResponse(
            codigo=102,
            mensagem=mensagem,
            protocolo=protocolo,
            raw=raw,
        )


class MockSefazClientAlwaysFail(MockSefazClient):
    """
    Mock de client SEFAZ que SEMPRE falha tecnicamente.

    Usado exclusivamente em testes de contingência, para validar que:
      - A service ativa contingência quando há erro técnico.
      - São criados NfceDocumento/NfceAuditoria apropriados para contingência.

    Ele oferece:
      - autorizar_nfce(...) -> levanta SefazTechnicalError
      - emitir_nfce(pre_emissao=...) -> levanta SefazTechnicalError

    Assim, cobre tanto o uso direto pela service (emitir_nfce) quanto
    um eventual uso via adapter que fale com autorizar_nfce.
    """

    def __init__(self, *, ambiente: str = "homolog", uf: Optional[str] = None):
        super().__init__(ambiente=ambiente, uf=uf)

    def _raise_technical_error(self, filial: Any | None = None) -> None:
        """
        Helper interno para construir o raw e levantar SefazTechnicalError.
        """
        fonte = filial or self

        raw = {
            "motivo": "Falha técnica simulada no mock.",
            "uf": getattr(fonte, "uf", None),
            "ambiente": getattr(fonte, "ambiente", None),
        }

        raise SefazTechnicalError(
            message="Falha técnica simulada na comunicação com a SEFAZ (mock).",
            codigo="TECH_FAIL",
            raw=raw,
        )

    def autorizar_nfce(
        self,
        *,
        filial,
        pre_emissao,
        numero: int,
        serie: int,
    ) -> SefazAutorizacaoResponse:
        """
        Método padrão usado pela camada de adapter (views) em ambiente
        de desenvolvimento/teste. Aqui sempre levantamos erro técnico.
        """
        self._raise_technical_error(filial=filial)

    # Este método NÃO faz parte do SefazClientProtocol, mas é aceito pela
    # service de emissão (duck typing). Isso permite passar esse mock
    # diretamente para a service emitir_nfce(user, request_id, sefaz_client=...).
    def emitir_nfce(self, *, pre_emissao) -> Dict[str, Any]:
        """
        Método usado diretamente pela service emitir_nfce em testes
        de contingência. Sempre levanta SefazTechnicalError.
        """
        self._raise_technical_error(filial=None)
