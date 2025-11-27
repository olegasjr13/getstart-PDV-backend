import uuid

from django.db import models

# -------------------------------------------------------------------
# Grupo de Produto
# -------------------------------------------------------------------


class GrupoProduto(models.Model):
    """
    Agrupador/categoria de produtos.

    - Não há mais hierarquia (grupo pai / subgrupo).
    - Pode ter foto/ícone para ser exibido no app (catálogo).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    nome = models.CharField(
        max_length=120,
        unique=True,
        db_index=True,
        help_text="Nome do grupo de produtos (ex.: Bebidas, Higiene, Padaria).",
    )

    descricao = models.TextField(
        blank=True,
        default="",
        help_text="Descrição opcional do grupo para uso interno.",
    )

    imagem = models.ImageField(
        upload_to="grupos_produtos/",
        null=True,
        blank=True,
        help_text="Imagem/ícone deste grupo para exibição no app.",
    )

    ativo = models.BooleanField(
        default=True,
        help_text="Indica se o grupo está disponível para uso em cadastros e vendas.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Grupo de Produto"
        verbose_name_plural = "Grupos de Produtos"
        ordering = ["nome"]
        indexes = [
            # Filtro frequente por grupos ativos em combos/listagens
            models.Index(fields=["ativo"], name="idx_grupo_prod_ativo"),
        ]

    def __str__(self) -> str:
        return self.nome
