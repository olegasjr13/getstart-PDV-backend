from django.db import models

from filial.models.filial_models import Filial

class FilialCertificadoA1(models.Model):
    """
    Armazena (de forma segura) o certificado digital A1 da filial.
    Separado da Filial para facilitar rotação/gestão de certificados.
    """

    filial = models.OneToOneField(
        Filial,
        on_delete=models.CASCADE,
        related_name="certificado_a1",
        help_text="Filial cujo certificado A1 é usado para assinar NF-e/NFC-e.",
    )

    # Arquivo PFX criptografado (você pode adicionar uma camada extra antes de salvar)
    a1_pfx = models.BinaryField(
        help_text="Arquivo PFX do certificado A1, criptografado.",
    )

    senha_hash = models.CharField(
        max_length=255,
        help_text="Hash ou dado cifrado da senha do certificado.",
    )

    a1_expires_at = models.DateTimeField(
        help_text="Data de expiração do certificado A1.",
    )

    numero_serie = models.CharField(
        max_length=100,
        blank=True,
        help_text="Número de série do certificado (opcional, para conferência).",
    )

    emissor = models.CharField(
        max_length=200,
        blank=True,
        help_text="Emissor (CA) do certificado (opcional).",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        verbose_name = "Certificado A1 da Filial"
        verbose_name_plural = "Certificados A1 das Filiais"

    def __str__(self):
        return f"Certificado A1 - {self.filial} (expira em {self.a1_expires_at.date()})"
