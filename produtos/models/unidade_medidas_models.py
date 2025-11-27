import uuid
from decimal import Decimal

from django.db import models
from django.core.exceptions import ValidationError

# -------------------------------------------------------------------
# Unidade de Medida
# -------------------------------------------------------------------

class UnidadeMedida(models.Model):
    """
    Unidade de medida comercial/tributária.

    Compatível com NF-e/NFC-e (campos uCom, uTrib etc).
    Exemplos de sigla: UN, KG, CX, PC, M, CM, L, ML, PCT, FD, SC...
    """

    TIPO_UNIDADE_CHOICES = (
        ("COMERCIAL", "Comercial"),
        ("TRIBUTARIA", "Tributária"),
        ("GERAL", "Geral"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sigla = models.CharField(
        max_length=6,
        unique=True,
        help_text="Sigla da unidade (ex: UN, KG, CX, M, L, PCT...)",
    )
    descricao = models.CharField(max_length=120)
    tipo = models.CharField(
        max_length=20,
        choices=TIPO_UNIDADE_CHOICES,
        default="GERAL",
        help_text="Classificação principal de uso da unidade.",
    )
    fator_conversao = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        default=Decimal("1.000000"),
        help_text="Fator de conversão em relação à unidade base (se aplicável).",
    )
    eh_padrao = models.BooleanField(
        default=False,
        help_text="Indica se esta unidade é uma das unidades padrão do sistema.",
    )
    ativo = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Unidade de Medida"
        verbose_name_plural = "Unidades de Medida"
        ordering = ["sigla"]
    
    def clean(self):
        super().clean()
        if self.fator_conversao <= 0:
            raise ValidationError("fator_conversao deve ser maior que zero.")

    def __str__(self) -> str:
        return f"{self.sigla} - {self.descricao}"

    @classmethod
    def bootstrap_unidades_padroes(cls):
        """
        Pode ser chamado em migration de dados ou comando de gestão
        para criar unidades mais comuns na legislação brasileira.
        NÃO é executado automaticamente.
        """
        unidades = [
            ("UN", "Unidade", "GERAL"),
            ("KG", "Quilograma", "GERAL"),
            ("G", "Grama", "GERAL"),
            ("MG", "Miligramas", "GERAL"),
            ("L", "Litro", "GERAL"),
            ("ML", "Mililitro", "GERAL"),
            ("M", "Metro", "GERAL"),
            ("CM", "Centímetro", "GERAL"),
            ("MM", "Milímetro", "GERAL"),
            ("CX", "Caixa", "COMERCIAL"),
            ("PC", "Peça", "COMERCIAL"),
            ("PCT", "Pacote", "COMERCIAL"),
            ("FD", "Fardo", "COMERCIAL"),
            ("SC", "Saco", "COMERCIAL"),
        ]
        for sigla, desc, tipo in unidades:
            cls.objects.get_or_create(
                sigla=sigla,
                defaults={
                    "descricao": desc,
                    "tipo": tipo,
                    "eh_padrao": True,
                },
            )

