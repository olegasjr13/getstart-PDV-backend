import uuid
from django.db import models
from django.utils import timezone


class NfceNumeroReserva(models.Model):
    """
    Reserva de numeração NFC-e por terminal/serie, idempotente via request_id (único por tenant).
    Em tenant schema (TENANT_APPS).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Chaves de contexto (não FK para evitar lock cruzado; guardar apenas UUID/valor)
    terminal_id = models.UUIDField()      # terminal.models.terminal_models.Terminal.id
    filial_id = models.UUIDField()        # filial.models.filial_models.Filial.id

    serie = models.PositiveIntegerField()
    numero = models.PositiveIntegerField()  # número reservado
    request_id = models.UUIDField(unique=True)  # idempotência por request_id (único no schema)

    

    # Dados da resposta SEFAZ (via parceiro fiscal)
    codigo_retorno = models.CharField(max_length=10, blank=True, null=True)
    mensagem_retorno = models.TextField(blank=True, null=True)

    xml_autorizado = models.TextField(blank=True, null=True)
    raw_sefaz_response = models.JSONField(blank=True, null=True)

    reserved_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "nfce_numero_reserva"
        indexes = [
            models.Index(fields=["terminal_id", "serie"]),
            models.Index(fields=["filial_id"]),
        ]

    def __str__(self):
        return f"Reserva NFC-e: term={self.terminal_id} serie={self.serie} num={self.numero}"


class NfceDocumento(models.Model):
    """
    Documento fiscal NFC-e consolidado após comunicação com a SEFAZ.

    - Um registro por combinação (filial, série, número).
    - Controla idempotência da emissão via request_id.
    - Serve de base para consultas, reimpressão, cancelamento e auditoria.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    filial = models.ForeignKey(
        "filial.Filial",
        on_delete=models.PROTECT,
        related_name="nfce_documentos",
    )
    terminal = models.ForeignKey(
        "terminal.Terminal",
        on_delete=models.PROTECT,
        related_name="nfce_documentos",
    )

    numero = models.PositiveIntegerField()
    serie = models.PositiveIntegerField()

    # Chave de acesso da NFC-e (44 dígitos)
    chave_acesso = models.CharField(max_length=47, unique=True)

    # Protocolo de autorização da SEFAZ
    protocolo = models.CharField(max_length=64, blank=True, null=True)

    # Status interno do documento (ex: autorizada, rejeitada, erro, cancelada)
    status = models.CharField(max_length=32)

    # Idempotência: mesmo request_id → mesmo documento
    request_id = models.UUIDField(unique=True)

    # Payload enviado ao parceiro fiscal (XML/JSON) e hash para idempotência/auditoria
    payload_enviado = models.JSONField(
        blank=True,
        null=True,
        help_text="Payload bruto enviado ao parceiro fiscal (XML/JSON).",
    )
    hash_payload_enviado = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        help_text="Hash SHA256 do payload_enviado, usado para idempotência e reconciliação.",
    )

    # XML autorizado devolvido pela SEFAZ (quando existir)
    xml_autorizado = models.TextField(blank=True, null=True)

    # Resposta bruta da SEFAZ (dict serializado)
    raw_sefaz_response = models.JSONField(blank=True, null=True)

    # Mensagem de retorno da SEFAZ (human-readable)
    mensagem_sefaz = models.TextField(blank=True, null=True)

    # Ambiente / UF (redundante, mas útil em consultas)
    ambiente = models.CharField(max_length=20, default="homolog")
    uf = models.CharField(max_length=2, blank=True, null=True)

    # =============================
    # CAMPOS DE CONTINGÊNCIA NFC-e
    # =============================
    em_contingencia = models.BooleanField(default=False)

    contingencia_ativada_em = models.DateTimeField(null=True, blank=True)

    contingencia_motivo = models.CharField(max_length=255, null=True, blank=True)

    contingencia_regularizada_em = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "nfce_documento"
        unique_together = (("filial", "serie", "numero"),)
        indexes = [
            models.Index(fields=["request_id"]),
            models.Index(fields=["chave_acesso"]),
            models.Index(fields=["filial", "serie", "numero"]),
        ]

    def __str__(self):
        return f"NFC-e {self.numero}/{self.serie} - {self.chave_acesso} ({self.status})"


class NfceAuditoria(models.Model):
    """
    Trilha de auditoria de eventos fiscais relacionados à NFC-e.

    Exemplos de tipo_evento:
      - EMISSAO_AUTORIZADA
      - EMISSAO_REJEITADA
      - CANCELAMENTO
      - INUTILIZACAO
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    tipo_evento = models.CharField(max_length=50)

    # Documento relacionado (pode ser nulo em casos de erro antes de criar doc)
    nfce_documento = models.ForeignKey(
        "fiscal.NfceDocumento",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="auditorias",
    )

    # Contexto multi-tenant / operacional
    tenant_id = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        help_text="Identificação do tenant (ex: schema_name ou CNPJ raiz).",
    )
    filial_id = models.UUIDField()
    terminal_id = models.UUIDField()
    user_id = models.IntegerField(blank=True, null=True)

    request_id = models.UUIDField()

    # Dados da resposta SEFAZ
    codigo_retorno = models.CharField(max_length=128, blank=True, null=True)
    mensagem_retorno = models.TextField(blank=True, null=True)

    xml_autorizado = models.TextField(blank=True, null=True)
    raw_sefaz_response = models.JSONField(blank=True, null=True)

    ambiente = models.CharField(max_length=20, blank=True, null=True)
    uf = models.CharField(max_length=2, blank=True, null=True)

    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "nfce_auditoria"
        indexes = [
            models.Index(fields=["request_id"]),
            models.Index(fields=["tipo_evento"]),
            models.Index(fields=["tenant_id"]),
        ]

    def __str__(self):
        return f"[{self.tipo_evento}] req={self.request_id} codigo={self.codigo_retorno}"
