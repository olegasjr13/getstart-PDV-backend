# fiscal/permissions.py
from rest_framework.permissions import BasePermission
from rest_framework.exceptions import PermissionDenied
from terminal.models.terminal_models import Terminal


class IsUserLinkedToTerminalFilial(BasePermission):
    """
    Checa se o usuário está vinculado à filial do terminal.
    - Se terminal não existir, deixa a view/service responder (404 TERMINAL_2001).
    - Se terminal_id estiver ausente ou malformado, o serializer lida (400).
    - Se usuário não vinculado, responde 403 com code AUTH_1006.
    """
    message = "Usuário sem permissão para a filial do terminal."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            # deixa o IsAuthenticated fazer seu papel (401/403)
            return False

        terminal_id = (request.data or {}).get("terminal_id")
        if not terminal_id:
            # serializer vai exigir mais à frente
            return True

        # NÃO convertemos para UUID manualmente — o serializer já fez isso.
        # Se o serializer ainda não rodou, esse valor pode ser string; usamos direto.
        try:
            filial_id = Terminal.objects.only("filial_id").get(id=terminal_id).filial_id
        except Terminal.DoesNotExist:
            # quem responde é a service/view com 404 + TERMINAL_2001
            return True

        if not user.userfilial_set.filter(filial_id=filial_id).exists():
            # devolve o code esperado nos testes
            raise PermissionDenied({"code": "AUTH_1006", "message": self.message})

        return True
