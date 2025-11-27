# produtos/models/produtos_models.py

import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models


class Produto(models.Model):
    """
    Cadastro de produtos, preparado para emissão de NF-e/NFC-e e regras futuras.

    Pontos importantes:
    - Vinculado a Grupo, NCM e Unidades (comercial/tributável).
    - CEST vem indiretamente via NCM -> CEST (relação ManyToMany).
    - Campos de origem, CFOP padrão, CST/CSOSN, PIS/COFINS/IPI etc.
    - Campos adicionais para preparação da CBS/IBS a partir de 2026.
    - Foto para uso no app.
    """

    ORIGEM_MERCADORIA_CHOICES = (
        ("0", "0 - Nacional, exceto as indicadas nos códigos 3, 4, 5 e 8"),
        ("1", "1 - Estrangeira - Importação direta"),
        ("2", "2 - Estrangeira - Adquirida no mercado interno"),
        ("3", "3 - Nacional, com conteúdo de importação superior a 40%"),
        ("4", "4 - Nacional, cuja produção tenha sido feita em conformidade com PPB"),
        ("5", "5 - Nacional, com conteúdo de importação inferior ou igual a 40%"),
        ("6", "6 - Estrangeira - Importação direta, sem similar nacional"),
        ("7", "7 - Estrangeira - Adquirida no mercado interno, sem similar nacional"),
        ("8", "8 - Nacional, conteúdo de importação superior a 70%"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    codigo_interno = models.CharField(
        max_length=40,
        unique=True,
        help_text="Código interno/SKU do produto.",
    )

    descricao = models.CharField(
        max_length=255,
        help_text="Descrição principal do produto (xProd).",
    )
    descricao_complementar = models.TextField(
        blank=True,
        default="",
        help_text="Descrição complementar/observações internas.",
    )

    grupo = models.ForeignKey(
        "produtos.GrupoProduto",
        on_delete=models.PROTECT,
        related_name="produtos",
        help_text="Grupo/categoria do produto.",
    )

    preco_venda = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        default=Decimal("0.000"),
        help_text="Preço de venda padrão do produto.",
    )

    desconto_maximo_percentual = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Percentual máximo de desconto permitido neste produto.",
        blank=True,
        null=True,
    )

    ncm = models.ForeignKey(
        "fiscal.NCM",
        on_delete=models.PROTECT,
        related_name="produtos",
        help_text="NCM do produto (obrigatório para NF-e/NFC-e).",
    )

    unidade_comercial = models.ForeignKey(
        "produtos.UnidadeMedida",
        on_delete=models.PROTECT,
        related_name="produtos_comerciais",
        help_text="Unidade de comercialização (uCom).",
    )
    unidade_tributavel = models.ForeignKey(
        "produtos.UnidadeMedida",
        on_delete=models.PROTECT,
        related_name="produtos_tributaveis",
        help_text="Unidade tributável (uTrib).",
    )
    fator_conversao_tributavel = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        default=Decimal("1.000000"),
        help_text=(
            "Fator de conversão entre a unidade comercial e a unidade tributável. "
            "Ex: 1 CX = 12 UN -> fator = 12.000000"
        ),
    )

    # Dados físicos básicos
    peso_liquido_kg = models.DecimalField(
        max_digits=11,
        decimal_places=3,
        default=Decimal("0.000"),
        help_text="Peso líquido em kg (tag 'qCom * peso_unitário', quando aplicável).",
    )
    peso_bruto_kg = models.DecimalField(
        max_digits=11,
        decimal_places=3,
        default=Decimal("0.000"),
        help_text="Peso bruto em kg para cálculo de frete/logística.",
    )

    # Origem mercadoria (tag orig)
    origem_mercadoria = models.CharField(
        max_length=1,
        choices=ORIGEM_MERCADORIA_CHOICES,
        default="0",
    )

    # CFOPs padrões para venda
    cfop_venda_dentro_estado = models.CharField(
        max_length=4,
        blank=True,
        null=True,
        help_text="CFOP padrão para venda dentro do estado.",
    )
    cfop_venda_fora_estado = models.CharField(
        max_length=4,
        blank=True,
        null=True,
        help_text="CFOP padrão para venda fora do estado.",
    )

    # ICMS
    csosn_icms = models.CharField(
        max_length=3,
        blank=True,
        null=True,
        help_text="CSOSN/CST ICMS padrão do produto em vendas.",
    )
    aliquota_icms = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Alíquota ICMS padrão para operações internas (quando aplicável).",
    )

    # PIS/COFINS
    cst_pis = models.CharField(
        max_length=2,
        blank=True,
        null=True,
        help_text="CST PIS padrão do produto.",
    )
    cst_cofins = models.CharField(
        max_length=2,
        blank=True,
        null=True,
        help_text="CST COFINS padrão do produto.",
    )
    aliquota_pis = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Alíquota de PIS em percentual (ex: 1.65).",
    )
    aliquota_cofins = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Alíquota de COFINS em percentual (ex: 7.60).",
    )

    # IPI
    cst_ipi = models.CharField(
        max_length=2,
        blank=True,
        null=True,
        help_text="CST IPI padrão do produto.",
    )
    codigo_enquadramento_ipi = models.CharField(
        max_length=3,
        blank=True,
        null=True,
        help_text="Código de enquadramento legal do IPI (clEnq).",
    )
    aliquota_ipi = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    # CBS/IBS (reforma)
    aliquota_cbs_especifica = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text=(
            "Alíquota CBS específica do produto (sobrepõe a padrão do NCM quando "
            "as regras de CBS entrarem em vigor)."
        ),
    )
    aliquota_ibs_especifica = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text=(
            "Alíquota IBS específica do produto (sobrepõe a padrão do NCM quando "
            "as regras de IBS entrarem em vigor)."
        ),
    )

    # Comportamento operacional
    permite_fracionar = models.BooleanField(
        default=False,
        help_text="Indica se o produto pode ser vendido fracionado (balança, peso etc).",
    )
    rastreavel = models.BooleanField(
        default=False,
        help_text="Indica se requer rastreabilidade/lote/série.",
    )

    # Foto para o app
    imagem = models.ImageField(
        upload_to="produtos/",
        null=True,
        blank=True,
        help_text="Imagem do produto para exibição no app.",
    )

    ativo = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Produto"
        verbose_name_plural = "Produtos"
        ordering = ["descricao"]
        indexes = [
            models.Index(fields=["codigo_interno"], name="idx_prod_codigo_interno"),
            models.Index(fields=["descricao"], name="idx_prod_descricao"),
            models.Index(fields=["ativo", "grupo"], name="idx_prod_ativo_grupo"),
            models.Index(fields=["ncm"], name="idx_prod_ncm"),
        ]

    def __str__(self) -> str:
        return f"{self.codigo_interno} - {self.descricao}"

    def clean(self):
        """
        Regras básicas de consistência de cadastro.
        """
        super().clean()

        # Fator de conversão deve ser > 0
        if self.fator_conversao_tributavel <= 0:
            raise ValidationError("fator_conversao_tributavel deve ser maior que zero.")

        # Alíquotas sempre entre 0% e 100%
        for field in [
            "aliquota_icms",
            "aliquota_pis",
            "aliquota_cofins",
            "aliquota_ipi",
            "aliquota_cbs_especifica",
            "aliquota_ibs_especifica",
        ]:
            valor = getattr(self, field)
            if valor < 0 or valor > 100:
                raise ValidationError({field: "Alíquota deve estar entre 0% e 100%."})

        # NCM obrigatório para produtos ativos utilizados em NF-e/NFC-e
        if self.ativo and not self.ncm_id:
            raise ValidationError(
                {"ncm": "NCM é obrigatório para produtos ativos utilizados em NF-e/NFC-e."}
            )

        # Validação básica de CFOP quando informado
        for cfop_field in ["cfop_venda_dentro_estado", "cfop_venda_fora_estado"]:
            cfop = getattr(self, cfop_field)
            if cfop and (len(cfop) != 4 or not cfop.isdigit()):
                raise ValidationError(
                    {cfop_field: "CFOP deve ter exatamente 4 dígitos numéricos."}
                )

        # Validação básica de códigos CSOSN/CST (somente dígitos)
        if self.csosn_icms and not self.csosn_icms.isdigit():
            raise ValidationError(
                {"csosn_icms": "CSOSN/CST ICMS deve conter apenas dígitos."}
            )

        for c_field in ["cst_pis", "cst_cofins", "cst_ipi"]:
            codigo = getattr(self, c_field)
            if codigo and (not codigo.isdigit() or len(codigo) not in (2, 3)):
                raise ValidationError(
                    {c_field: "CST deve conter apenas dígitos (2 ou 3 caracteres)."}
                )


    # -------------------------
    # CEST via NCM
    # -------------------------
    @property
    def cest_list(self):
        """
        Retorna a lista de CESTs relacionados ao NCM do produto.
        Útil para validações fiscais na emissão de NF-e/NFC-e.
        """
        if not self.ncm_id:
            return []
        return list(self.ncm.cests.values_list("codigo", flat=True))

    # -------------------------
    # Códigos de barras (multi)
    # -------------------------
    @property
    def codigos_barras_ativos(self):
        """
        Retorna o queryset de códigos de barras ativos do produto.
        """
        return self.codigos_barras.filter(ativo=True)

    @property
    def codigo_barras_comercial(self):
        """
        Retorna o código de barras principal de venda (cEAN).
        """
        qs = self.codigos_barras_ativos

        # principal COMERCIAL/AMBOS
        cod = (
            qs.filter(funcao__in=["COMERCIAL", "AMBOS"], principal=True)
            .order_by("codigo")
            .values_list("codigo", flat=True)
            .first()
        )
        if cod:
            return cod

        # qualquer COMERCIAL/AMBOS
        cod = (
            qs.filter(funcao__in=["COMERCIAL", "AMBOS"])
            .order_by("codigo")
            .values_list("codigo", flat=True)
            .first()
        )
        return cod

    @property
    def codigo_barras_tributavel(self):
        """
        Retorna o código de barras principal da unidade tributável (cEANTrib).
        """
        qs = self.codigos_barras_ativos

        cod = (
            qs.filter(funcao__in=["TRIBUTAVEL", "AMBOS"], principal=True)
            .order_by("codigo")
            .values_list("codigo", flat=True)
            .first()
        )
        if cod:
            return cod

        cod = (
            qs.filter(funcao__in=["TRIBUTAVEL", "AMBOS"])
            .order_by("codigo")
            .values_list("codigo", flat=True)
            .first()
        )
        return cod
    
    def get_parametros_fiscais_base(self):
        """
        Consolida os parâmetros fiscais básicos do produto.

        Neste momento, utiliza apenas os campos do próprio Produto e o código
        do NCM associado (quando houver). Em próximos épicos, este método
        poderá ser estendido para considerar regras de NCM, UF, tipo de
        operação e regime tributário.
        """
        ncm = self.ncm if getattr(self, "ncm_id", None) else None

        return {
            "ncm_codigo": ncm.codigo if ncm else None,
            "origem_mercadoria": self.origem_mercadoria,
            "cfop_venda_dentro_estado": self.cfop_venda_dentro_estado,
            "cfop_venda_fora_estado": self.cfop_venda_fora_estado,
            "csosn_icms": self.csosn_icms,
            "cst_pis": self.cst_pis,
            "cst_cofins": self.cst_cofins,
            "cst_ipi": self.cst_ipi,
            "aliquota_icms": self.aliquota_icms,
            "aliquota_pis": self.aliquota_pis,
            "aliquota_cofins": self.aliquota_cofins,
            "aliquota_ipi": self.aliquota_ipi,
            "aliquota_cbs": self.aliquota_cbs_especifica,
            "aliquota_ibs": self.aliquota_ibs_especifica,
        }

    def get_cests_ativos(self):
        """
        Retorna a lista de CESTs ativos vinculados ao NCM do produto.
        """
        if not getattr(self, "ncm_id", None):
            return []
        # Assume que o relacionamento NCM -> CEST é via related_name 'cests'
        return list(self.ncm.cests.filter(ativo=True))

    def get_cest_principal(self):
        """
        Retorna o CEST considerado principal para este produto.

        Regra atual (simples, mas determinística):
        - se houver apenas um CEST ativo para o NCM: retorna ele;
        - se houver vários: retorna o de menor código;
        - se não houver: retorna None.
        """
        cests = self.get_cests_ativos()
        if not cests:
            return None
        if len(cests) == 1:
            return cests[0]
        return sorted(cests, key=lambda c: c.codigo)[0]

