# vendas/services/finalizar_venda_nfce_service.py

from __future__ import annotations

import logging
from typing import Optional, Union
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import transaction

from vendas.models.venda_models import Venda, VendaStatus
from usuario.models.usuario_models import User
from vendas.services.venda_state_machine import VendaStateMachine  # NOVO IMPORT

logger = logging.getLogger(__name__)


def finalizar_venda_e_emitir_nfce(
    *,
    venda: Venda,
    operador: Optional[User] = None,
    request_id: Optional[Union[str, UUID]] = None,
):
    """
    Orquestra o fluxo:

    - Garante que a venda está em estado válido para emissão de NFC-e.
    - Trata idempotência: se a venda já estiver FINALIZADA, não chama fiscal novamente.
    - Atualiza status da venda para AGUARDANDO_EMISSAO_FISCAL.
    - Chama o fluxo fiscal (emitir_nfce_para_venda).
    - Ajusta status final da venda: FINALIZADA ou ERRO_FISCAL.
    - Propaga o objeto retornado pelo fluxo fiscal (nfce_doc / result).

    Em caso de erro inesperado (ex.: timeout, infra):
    - Marca venda como ERRO_FISCAL com mensagem genérica.
    - Faz commit dessas alterações.
    - Propaga a exceção para o chamador.

    Observação:
    - NÃO depende de FK venda ↔ NfceDocumento.
    - Idempotência é feita exclusivamente pelo status da venda.
    """

    from fiscal.services.nfce_venda_service import emitir_nfce_para_venda

    logger.info(
        "Iniciando orquestração de emissão NFC-e para venda. "
        "venda_id=%s status_atual=%s documento_fiscal_tipo=%s request_id=%s",
        venda.id,
        venda.status,
        getattr(venda, "documento_fiscal_tipo", None),
        request_id,
    )

    # Idempotência antes de qualquer coisa: se já FINALIZADA, não faz nada
    venda_db = Venda.objects.select_related("filial", "terminal").get(pk=venda.pk)
    if venda_db.status == VendaStatus.FINALIZADA:
        logger.info(
            "Venda já está FINALIZADA. Tratando chamada como idempotente. "
            "venda_id=%s request_id=%s",
            venda_db.id,
            request_id,
        )
        return None

    # Valida status e tipo fiscal ANTES de entrar em transação
    if venda_db.status not in {
        VendaStatus.PAGAMENTO_CONFIRMADO,
        VendaStatus.AGUARDANDO_EMISSAO_FISCAL,
    }:
        raise ValidationError(
            f"Venda não está em status válido para emissão de NFC-e. "
            f"Status atual: {venda_db.status}"
        )

    if getattr(venda_db, "documento_fiscal_tipo", None) != "NFCE":
        raise ValidationError(
            "Somente vendas configuradas para documento_fiscal_tipo = 'NFCE' "
            "podem ser processadas neste fluxo."
        )

    nfce_doc = None
    erro_interno: Optional[Exception] = None

    # ------------------------------------------------------------------
    # Bloco transacional: garante consistência de concorrência
    # ------------------------------------------------------------------
    with transaction.atomic():
        # Recarrega sob lock
        venda_db = (
            Venda.objects.select_for_update()
            .select_related("filial", "terminal")
            .get(pk=venda.pk)
        )

        # Re-checa idempotência dentro do lock
        if venda_db.status == VendaStatus.FINALIZADA:
            logger.info(
                "Venda já está FINALIZADA (dentro do lock). "
                "Tratando chamada como idempotente. venda_id=%s request_id=%s",
                venda_db.id,
                request_id,
            )
            return None

        status_original = venda_db.status

        # Atualiza para AGUARDANDO_EMISSAO_FISCAL via state machine (sem salvar ainda)
        VendaStateMachine.para_aguardando_emissao_fiscal(
            venda_db,
            motivo="Preparando emissão NFC-e.",
            save=False,
        )

        # Zera campos de erro fiscal (se existirem)
        if hasattr(venda_db, "codigo_erro_fiscal"):
            venda_db.codigo_erro_fiscal = None
        if hasattr(venda_db, "mensagem_erro_fiscal"):
            venda_db.mensagem_erro_fiscal = None

        campos_update = ["status"]
        if hasattr(venda_db, "codigo_erro_fiscal"):
            campos_update.append("codigo_erro_fiscal")
        if hasattr(venda_db, "mensagem_erro_fiscal"):
            campos_update.append("mensagem_erro_fiscal")

        venda_db.save(update_fields=campos_update)

        logger.info(
            "Status da venda atualizado para AGUARDANDO_EMISSAO_FISCAL. "
            "venda_id=%s status_anterior=%s request_id=%s",
            venda_db.id,
            status_original,
            request_id,
        )

        # -----------------------------
        # Chama fluxo fiscal
        # -----------------------------
        try:
            nfce_doc = emitir_nfce_para_venda(
                venda=venda_db,
                operador=operador,
                request_id=str(request_id) if request_id is not None else None,
            )
        except Exception as exc:
            # Marca erro fiscal e salva, mas NÃO re-raise aqui dentro
            logger.exception(
                "Falha inesperada ao emitir NFC-e para venda_id=%s request_id=%s: %s",
                venda_db.id,
                request_id,
                exc,
            )

            # Via state machine (sem salvar aqui)
            VendaStateMachine.para_erro_fiscal(
                venda_db,
                motivo="Falha interna ao emitir NFC-e.",
                save=False,
            )
            if hasattr(venda_db, "mensagem_erro_fiscal"):
                venda_db.mensagem_erro_fiscal = (
                    "Falha interna ao emitir NFC-e. Ver logs."
                )

            campos_update = ["status"]
            if hasattr(venda_db, "mensagem_erro_fiscal"):
                campos_update.append("mensagem_erro_fiscal")

            venda_db.save(update_fields=campos_update)

            erro_interno = exc
        else:
            # Sucesso na chamada fiscal -> decide status com base no retorno
            status_nfce_raw = getattr(nfce_doc, "status", None)
            status_nfce = (status_nfce_raw or "").upper()

            codigo_erro = getattr(nfce_doc, "codigo_erro", None)
            mensagem_erro = getattr(nfce_doc, "mensagem_erro", None)

            if status_nfce in {"AUTORIZADA", "AUT"}:
                venda_db.status = VendaStatus.FINALIZADA
                if hasattr(venda_db, "codigo_erro_fiscal"):
                    venda_db.codigo_erro_fiscal = None
                if hasattr(venda_db, "mensagem_erro_fiscal"):
                    venda_db.mensagem_erro_fiscal = None
            else:
                venda_db.status = VendaStatus.ERRO_FISCAL
                if hasattr(venda_db, "codigo_erro_fiscal"):
                    venda_db.codigo_erro_fiscal = codigo_erro
                if hasattr(venda_db, "mensagem_erro_fiscal"):
                    venda_db.mensagem_erro_fiscal = mensagem_erro

            campos_update = ["status"]
            if hasattr(venda_db, "codigo_erro_fiscal"):
                campos_update.append("codigo_erro_fiscal")
            if hasattr(venda_db, "mensagem_erro_fiscal"):
                campos_update.append("mensagem_erro_fiscal")

            venda_db.save(update_fields=campos_update)

            logger.info(
                "Finalização de venda após emissão NFC-e. venda_id=%s status_venda=%s "
                "status_nfce=%s codigo_erro=%s mensagem_erro=%s request_id=%s",
                venda_db.id,
                venda_db.status,
                status_nfce,
                codigo_erro,
                mensagem_erro,
                request_id,
            )

    # ------------------------------------------------------------------
    # Fora do atomic: se houve erro interno, propaga a exceção
    # (as alterações já foram commitadas).
    # ------------------------------------------------------------------
    if erro_interno is not None:
        raise erro_interno

    return nfce_doc
