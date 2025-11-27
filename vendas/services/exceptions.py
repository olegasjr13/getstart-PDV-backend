# vendas/services/exceptions.py

class DescontoError(Exception):
    """
    Erro genérico de desconto.
    Base para erros específicos.
    """
    pass


class DescontoNaoPermitidoError(DescontoError):
    """
    Desconto totalmente proibido no contexto atual.
    (Nenhuma configuração permite o percentual solicitado.)
    """

    def __init__(self, mensagem: str, percentual_solicitado=None):
        self.mensagem = mensagem
        self.percentual_solicitado = percentual_solicitado
        super().__init__(mensagem)


class DescontoRequerAutenticacaoOperadorError(DescontoError):
    """
    Desconto permitido, mas exige autenticação (senha) do operador.
    """

    def __init__(self, mensagem: str, percentual_solicitado=None, limite_operador=None):
        self.mensagem = mensagem
        self.percentual_solicitado = percentual_solicitado
        self.limite_operador = limite_operador
        super().__init__(mensagem)


class DescontoRequerAprovadorError(DescontoError):
    """
    Desconto permitido, mas exige aprovador (supervisor/gerente) com limite suficiente.
    """

    def __init__(
        self,
        mensagem: str,
        percentual_solicitado=None,
        limite_aprovador=None,
    ):
        self.mensagem = mensagem
        self.percentual_solicitado = percentual_solicitado
        self.limite_aprovador = limite_aprovador
        super().__init__(mensagem)


class MotivoDescontoObrigatorioError(DescontoError):
    """
    Motivo de desconto é obrigatório sempre que houver desconto > 0.
    """

    def __init__(self, mensagem: str = "Motivo de desconto é obrigatório."):
        self.mensagem = mensagem
        super().__init__(mensagem)
