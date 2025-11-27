# vendas/api/v1/views.py

import logging
from uuid import uuid4

from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError as DjangoValidationError

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from vendas.models.venda_models import Venda, VendaStatus
from vendas.services.finalizar_venda_nfce_service import (
    finalizar_venda_e_emitir_nfce,
)

logger = logging.getLogger(__name__)


class FinalizarVendaNfceView(APIView):
    """
    Endpoint HTTP chamado pelo PDV para finalizar a venda e emitir NFC-e.

    Fluxo esperado:
    - Recebe venda_id na URL.
    - Usa o usuário autenticado como operador (request.user).
    - Gera/usa um request_id (cabeçalho X-Request-ID ou UUID novo).
    - Chama finalizar_venda_e_emitir_nfce().
    - Mapeia o resultado (ou erro) para um JSON padronizado.

    Códigos de resposta:
    - 200 OK:
        - Venda FINALIZADA (NFCE emitida, ou chamada idempotente).
    - 400 BAD REQUEST:
        - Erro de validação de negócio (ex.: venda não paga, tipo fiscal inválido).
    - 404 NOT FOUND:
        - Venda não encontrada no tenant atual.
    - 422 UNPROCESSABLE ENTITY:
        - Erro fiscal conhecido (NFCE rejeitada).
    - 502 BAD GATEWAY:
        - Erro interno/infra ao falar com camada fiscal (timeout, etc.),
          mas venda já marcada como ERRO_FISCAL.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, venda_id, *args, **kwargs):
        # request_id para rastreio em logs + correlação com middleware
        request_id = (
            request.headers.get("X-Request-ID") or str(uuid4())
        )

        operador = request.user

        # Busca a venda no tenant atual
        venda = get_object_or_404(Venda, pk=venda_id)

        logger.info(
            "HTTP PDV: solicitar finalização de venda + NFC-e. "
            "venda_id=%s status_atual=%s documento_fiscal_tipo=%s operador_id=%s request_id=%s",
            venda.id,
            venda.status,
            getattr(venda, "documento_fiscal_tipo", None),
            getattr(operador, "id", None),
            request_id,
        )

        try:
            nfce_doc = finalizar_venda_e_emitir_nfce(
                venda=venda,
                operador=operador,
                request_id=request_id,
            )
        except DjangoValidationError as exc:
            # Erros de fluxo de negócio / pré-condição
            logger.warning(
                "HTTP PDV: erro de validação ao finalizar venda + NFC-e. "
                "venda_id=%s erro=%s request_id=%s",
                venda_id,
                exc,
                request_id,
            )
            detail = exc.message if hasattr(exc, "message") else str(exc)
            return Response(
                {
                    "code": "ERRO_VALIDACAO_VENDA_NFCE",
                    "detail": detail,
                    "venda_id": str(venda_id),
                    "request_id": str(request_id),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as exc:
            # Erros inesperados / infra (timeout SEFAZ, erro de serviço fiscal, etc.)
            logger.exception(
                "HTTP PDV: erro interno ao finalizar venda + NFC-e. "
                "venda_id=%s request_id=%s erro=%s",
                venda_id,
                request_id,
                exc,
            )

            # Recarrega a venda para refletir status ERRO_FISCAL gravado no service
            venda.refresh_from_db()

            return Response(
                {
                    "code": "ERRO_INTERNO_FISCAL",
                    "detail": "Falha interna ao emitir NFC-e. Verifique status da venda.",
                    "venda": {
                        "id": str(venda.id),
                        "status": venda.status,
                        "codigo_erro_fiscal": getattr(
                            venda, "codigo_erro_fiscal", None
                        ),
                        "mensagem_erro_fiscal": getattr(
                            venda, "mensagem_erro_fiscal", None
                        ),
                    },
                    "request_id": str(request_id),
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # Se não houve exceção, recarrega a venda para inspecionar status final
        venda.refresh_from_db()

        # Monta payload base da venda
        venda_payload = {
            "id": str(venda.id),
            "status": venda.status,
            "documento_fiscal_tipo": getattr(
                venda, "documento_fiscal_tipo", None
            ),
            "codigo_erro_fiscal": getattr(venda, "codigo_erro_fiscal", None),
            "mensagem_erro_fiscal": getattr(
                venda, "mensagem_erro_fiscal", None
            ),
        }

        # Monta payload da NFC-e retornada (se houver objeto nfce_doc)
        nfce_payload = None
        if nfce_doc is not None:
            nfce_payload = {
                "status": getattr(nfce_doc, "status", None),
                "codigo_erro": getattr(nfce_doc, "codigo_erro", None),
                "mensagem_erro": getattr(nfce_doc, "mensagem_erro", None),
                "chave_acesso": getattr(nfce_doc, "chave_acesso", None),
                "numero": getattr(nfce_doc, "numero", None),
                "serie": getattr(nfce_doc, "serie", None),
                "protocolo": getattr(nfce_doc, "protocolo", None),
            }

        # 1) Venda FINALIZADA → NFCE emitida (happy path ou idempotente)
        if venda.status == VendaStatus.FINALIZADA:
            # Se nfce_doc for None (idempotência), retornamos só dados da venda
            return Response(
                {
                    "code": "NFCE_EMITIDA",
                    "detail": "Venda finalizada com NFC-e autorizada.",
                    "venda": venda_payload,
                    "nfce": nfce_payload,
                    "request_id": str(request_id),
                },
                status=status.HTTP_200_OK,
            )

        # 2) Venda com ERRO_FISCAL → NFCE rejeitada ou falha
        if venda.status == VendaStatus.ERRO_FISCAL:
            return Response(
                {
                    "code": "ERRO_FISCAL",
                    "detail": "Houve erro fiscal na emissão da NFC-e.",
                    "venda": venda_payload,
                    "nfce": nfce_payload,
                    "request_id": str(request_id),
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        # 3) Qualquer outro status aqui é inesperado → 500 para diagnóstico
        logger.error(
            "HTTP PDV: finalização de venda resultou em status inesperado. "
            "venda_id=%s status_venda=%s request_id=%s",
            venda.id,
            venda.status,
            request_id,
        )
        return Response(
            {
                "code": "ESTADO_INESPERADO_VENDA_NFCE",
                "detail": (
                    "A venda terminou em um estado inesperado após tentar "
                    "emitir NFC-e. Verifique logs."
                ),
                "venda": venda_payload,
                "nfce": nfce_payload,
                "request_id": str(request_id),
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
