# fiscal/services/numero_service.py
from dataclasses import dataclass
from django.db import transaction, IntegrityError
from django.utils import timezone

from terminal.models.terminal_models import Terminal
from filial.models.filial_models import Filial
from fiscal.models import NfceNumeroReserva
from rest_framework.exceptions import PermissionDenied

# Códigos de erro do domínio
ERR_A1_EXPIRED = "FISCAL_3001"
ERR_SERIE_MISMATCH = "FISCAL_3002"
ERR_TERMINAL_NOT_FOUND = "TERMINAL_2001"
ERR_NO_PERMISSION = "AUTH_1006"

@dataclass
class ReservaNumeroResult:
    numero: int
    serie: int
    terminal_id: str
    filial_id: str
    request_id: str
    reserved_at: str  # ISO string (preencher na view)

def _assert_a1_valid(filial: Filial):
    """
    Bloqueia a emissão se o A1 estiver expirado.
    """
    cert = getattr(filial, "certificado_a1", None)
    if not cert:
        raise PermissionDenied({
            "code": ERR_A1_EXPIRED,
            "message": "Filial não possui certificado A1 configurado."
        })

    if not cert.a1_expires_at or cert.a1_expires_at <= timezone.now():
        raise PermissionDenied({
            "code": ERR_A1_EXPIRED,
            "message": "Certificado A1 expirado. Emissão bloqueada."
        })

def reservar_numero_nfce(*, user, terminal_id, serie: int, request_id) -> ReservaNumeroResult:
    """
    Regras:
      - Usuário deve estar vinculado à filial do terminal.
      - Série informada deve ser igual à série do terminal.
      - Certificado A1 válido → senão, bloqueia pré-emissão.
      - Idempotência via unique(request_id): múltiplas chamadas com o mesmo request_id
        retornam SEMPRE a mesma reserva.
      - Concorrência protegida com select_for_update no Terminal e savepoint na criação da reserva.
      - Apenas quando a criação da reserva for nossa é que avançamos o numero_atual do Terminal.
    """
    # 1) Terminal
    try:
        terminal = Terminal.objects.select_related(None).get(id=terminal_id)
    except Terminal.DoesNotExist:
        from rest_framework.exceptions import NotFound
        raise NotFound({"code": ERR_TERMINAL_NOT_FOUND, "message": "Terminal não encontrado"})

    # 2) Vínculo usuário ↔ filial do terminal
    filial_id = terminal.filial_id
    if not user.userfilial_set.filter(filial_id=filial_id).exists():
        from rest_framework.exceptions import PermissionDenied
        raise PermissionDenied({"code": ERR_NO_PERMISSION, "message": "Usuário sem permissão para a filial do terminal"})

    # 3) Série coerente
    if terminal.serie != serie:
        from rest_framework.exceptions import ValidationError
        raise ValidationError({"code": ERR_SERIE_MISMATCH, "message": "Série informada não coincide com a série do terminal."})

    # 4) Bloqueio por A1 expirado (antes de qualquer toque em número)
    filial = Filial.objects.only("id", "a1_expires_at").get(id=filial_id)
    _assert_a1_valid(filial)

    # 5) Curto-circuito de idempotência (se já existe, retorna)
    try:
        existing = NfceNumeroReserva.objects.get(request_id=request_id)
        return ReservaNumeroResult(
            numero=existing.numero,
            serie=existing.serie,
            terminal_id=str(existing.terminal_id),
            filial_id=str(existing.filial_id),
            request_id=str(existing.request_id),
            reserved_at=existing.reserved_at.isoformat(),
        )
    except NfceNumeroReserva.DoesNotExist:
        pass

    # 6) Concorrência: lock pessimista no terminal, criação da reserva em savepoint,
    #    avanço do numero_atual somente se a criação FICOU conosco.
    with transaction.atomic():
        # trava a linha do terminal
        term_locked = (
            Terminal.objects.select_for_update(skip_locked=False)
            .only("id", "numero_atual", "serie", "filial_id")
            .get(id=terminal_id)
        )

        # revalida série sob lock
        if term_locked.serie != serie:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"code": ERR_SERIE_MISMATCH, "message": "Série informada não coincide com a série do terminal."})

        created_by_us = False

        # savepoint interno: se outra thread já criou a mesma request_id,
        # o IntegrityError não "quebra" a transação externa.
        try:
            with transaction.atomic():
                # cria com numero=0 como placeholder; só setamos o número após a criação
                reserva = NfceNumeroReserva.objects.create(
                    terminal_id=terminal_id,
                    filial_id=filial_id,
                    serie=serie,
                    numero=0,
                    request_id=request_id,
                )
                created_by_us = True
        except IntegrityError:
            # Outra thread criou primeiro. Buscamos a existente e devolvemos.
            reserva = NfceNumeroReserva.objects.get(request_id=request_id)
            created_by_us = False

        if created_by_us:
            # Só quem criou avança o contador e preenche o número
            proximo = (term_locked.numero_atual or 0) + 1
            term_locked.numero_atual = proximo
            term_locked.save(update_fields=["numero_atual"])

            reserva.numero = proximo
            # (os demais campos já vieram corretos)
            reserva.save(update_fields=["numero"])

    # 7) Retorno
    return ReservaNumeroResult(
        numero=reserva.numero,
        serie=reserva.serie,
        terminal_id=str(reserva.terminal_id),
        filial_id=str(reserva.filial_id),
        request_id=str(reserva.request_id),
        reserved_at=reserva.reserved_at.isoformat(),
    )
