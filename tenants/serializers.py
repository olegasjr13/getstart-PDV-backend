# tenants/serializers.py
from rest_framework import serializers


class EnderecoPaisSerializer(serializers.Serializer):
    codigo_nfe = serializers.CharField(max_length=4)      # ex: "1058"
    nome = serializers.CharField(max_length=60)           # ex: "BRASIL"
    sigla2 = serializers.CharField(
        max_length=2, required=False, allow_blank=True    # ex: "BR"
    )
    sigla3 = serializers.CharField(
        max_length=3, required=False, allow_blank=True    # ex: "BRA"
    )


class EnderecoUFSerializer(serializers.Serializer):
    sigla = serializers.CharField(max_length=2)           # ex: "SP"
    nome = serializers.CharField(max_length=60)           # ex: "São Paulo"
    codigo_ibge = serializers.CharField(min_length=2, max_length=2)  # ex: "35"
    # país ao qual esta UF pertence
    pais = EnderecoPaisSerializer()


class EnderecoMunicipioSerializer(serializers.Serializer):
    nome = serializers.CharField(max_length=60)           # ex: "São Paulo"
    codigo_ibge = serializers.CharField(min_length=7, max_length=7)  # ex: "3550308"
    codigo_siafi = serializers.CharField(
        max_length=10, required=False, allow_blank=True
    )


class EnderecoCreateSerializer(serializers.Serializer):
    """
    Endereço no formato de cadastro do formulário (campos estilo NFe),
    mapeado para o modelo normalizado:
      Pais -> UF -> Municipio -> Bairro -> Logradouro -> Endereco.
    """
    pais = EnderecoPaisSerializer()
    uf = EnderecoUFSerializer()
    municipio = EnderecoMunicipioSerializer()

    bairro = serializers.CharField(max_length=60)         # xBairro

    logradouro_tipo = serializers.ChoiceField(
        choices=["RUA", "AV", "ROD", "OUTROS"],           # mapeia para Logradouro.tipo
    )
    logradouro_nome = serializers.CharField(max_length=80)    # nome sem o tipo
    logradouro_cep = serializers.CharField(min_length=8, max_length=8)

    numero = serializers.CharField(max_length=10)         # nro
    complemento = serializers.CharField(
        max_length=60, required=False, allow_blank=True
    )
    referencia = serializers.CharField(
        max_length=120, required=False, allow_blank=True
    )
    cep = serializers.CharField(min_length=8, max_length=8)


class FilialCreateSerializer(serializers.Serializer):
    """
    Dados cadastrais da empresa (filial emitente) informados no formulário inicial.
    """
    razao_social = serializers.CharField(max_length=120)
    nome_fantasia = serializers.CharField(max_length=120)
    cnpj = serializers.CharField(min_length=14, max_length=14)
    endereco = EnderecoCreateSerializer()


class TenantCreateSerializer(serializers.Serializer):
    # dados do tenant (já existiam)
    cnpj_raiz = serializers.CharField(min_length=14, max_length=14)
    nome = serializers.CharField(max_length=150)
    domain = serializers.CharField(max_length=255)
    premium_db_alias = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )

    # NOVO: bloco da filial inicial
    filial = FilialCreateSerializer()

    def validate(self, attrs):
        """
        Validações cruzadas simples:
        Ex: garantir que o CNPJ da filial começa com a raiz do tenant.
        (Pode deixar opcional, mas já deixo preparado.)
        """
        cnpj_raiz = attrs["cnpj_raiz"]
        filial_cnpj = attrs["filial"]["cnpj"]

        if not filial_cnpj.startswith(cnpj_raiz):
            # Se quiser forçar a regra, descomenta o raise abaixo:
            # raise serializers.ValidationError(
            #     "CNPJ da filial deve começar com a raiz informada (cnpj_raiz)."
            # )
            pass

        return attrs
