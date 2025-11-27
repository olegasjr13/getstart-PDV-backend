from rest_framework import serializers
from django.db import transaction

from filial.models import Filial
from filial.models.filial_nfe_models import FilialNFeConfig
from filial.models.filial_nfce_models import FilialNFCeConfig
from filial.models.filial_fiscal_models import FilialFiscalConfig
from filial.models.filial_certificado_models import FilialCertificadoA1
from enderecos.serializers import EnderecoSerializer
from enderecos.models.endereco_models import Endereco

# --- 1. Serializers Satélites (Configurações) ---

class FilialNFeConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = FilialNFeConfig
        exclude = ['filial', 'created_at', 'updated_at']
        # Excluímos 'filial' porque ela será injetada automaticamente pelo pai

class FilialNFCeConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = FilialNFCeConfig
        exclude = ['filial', 'created_at', 'updated_at']

        def validate(self, attrs):
            # Monta pseudo-instância para chamar clean()
            instance = FilialNFCeConfig(
                **{
                    **getattr(self.instance, "__dict__", {}),
                    **attrs,
                }
            )
            instance.__dict__.pop("_state", None)
            instance.clean()
            return attrs

class FilialFiscalConfigSerializer(serializers.ModelSerializer):
    # Campos de display para facilitar leitura no frontend
    regime_tributario_desc = serializers.CharField(source='get_regime_tributario_display', read_only=True)
    tipo_contrib_icms_desc = serializers.CharField(source='get_tipo_contrib_icms_display', read_only=True)

    class Meta:
        model = FilialFiscalConfig
        exclude = ['filial', 'created_at', 'updated_at']

class FilialCertificadoA1Serializer(serializers.ModelSerializer):
    """
    Serializer para o Certificado.
    ATENÇÃO: O campo binário (PFX) e a senha são sensíveis.
    Configuramos como write_only para que não sejam expostos no GET.
    """
    a1_pfx = serializers.CharField(write_only=True, help_text="Conteúdo do arquivo PFX em Base64")
    senha_hash = serializers.CharField(write_only=True)
    
    # Campos apenas leitura úteis para gestão
    status_validade = serializers.SerializerMethodField()

    class Meta:
        model = FilialCertificadoA1
        fields = [
            'id', 'a1_pfx', 'senha_hash', 'a1_expires_at', 
            'numero_serie', 'emissor', 'status_validade'
        ]
        read_only_fields = ['a1_expires_at', 'numero_serie', 'emissor']

    def get_status_validade(self, obj):
        from django.utils import timezone
        if obj.a1_expires_at < timezone.now():
            return "VENCIDO"
        return "VÁLIDO"
    
    # Nota: A lógica real de extrair dados do PFX e salvar binário 
    # deve ser feita na View ou num método create específico se receber base64.

# --- 2. Serializer Principal (Filial Completa) ---

class FilialSerializer(serializers.ModelSerializer):
    """
    Serializer Mestre da Filial.
    Permite criar/editar a filial e todas as suas configurações em uma única requisição.
    """
    # Campo para selecionar o endereço pelo ID (escrita)
    endereco_id = serializers.PrimaryKeyRelatedField(
        queryset=Endereco.objects.all(), 
        source='endereco',
        write_only=True,
        help_text="ID do endereço já cadastrado."
    )
    # Campo para exibir os dados do endereço (leitura)
    endereco_detalhes = EnderecoSerializer(source='endereco', read_only=True)

    # Nested Serializers (Configurações)
    # required=False permite criar uma filial "pelada" e configurar depois
    nfe_config = FilialNFeConfigSerializer(required=False)
    nfce_config = FilialNFCeConfigSerializer(required=False)
    fiscal_config = FilialFiscalConfigSerializer(required=False)
    # Certificado geralmente é upload separado, mas mantemos aqui para estrutura
    certificado_a1 = FilialCertificadoA1Serializer(required=False, read_only=True)

    class Meta:
        model = Filial
        fields = [
            'id', 
            'razao_social', 'nome_fantasia', 'cnpj', 'ativo',
            'endereco_id', 'endereco_detalhes',
            'nfe_config', 'nfce_config', 'fiscal_config', 'certificado_a1',
            'created_at', 'updated_at'
        ]

    @transaction.atomic
    def create(self, validated_data):
        """
        Sobrescreve o método create para lidar com os nested serializers.
        Remove os dados das configs do payload principal e cria os objetos relacionados.
        """
        # 1. Extrai dados aninhados
        nfe_data = validated_data.pop('nfe_config', None)
        nfce_data = validated_data.pop('nfce_config', None)
        fiscal_data = validated_data.pop('fiscal_config', None)
        
        # 2. Cria a Filial
        filial = Filial.objects.create(**validated_data)

        # 3. Cria as Configurações Satélites (se enviadas)
        if nfe_data:
            FilialNFeConfig.objects.create(filial=filial, **nfe_data)
        
        if nfce_data:
            FilialNFCeConfig.objects.create(filial=filial, **nfce_data)
            
        if fiscal_data:
            FilialFiscalConfig.objects.create(filial=filial, **fiscal_data)

        return filial

    @transaction.atomic
    def update(self, instance, validated_data):
        """
        Sobrescreve o update para permitir atualização aninhada.
        """
        # 1. Extrai dados aninhados
        nfe_data = validated_data.pop('nfe_config', None)
        nfce_data = validated_data.pop('nfce_config', None)
        fiscal_data = validated_data.pop('fiscal_config', None)

        # 2. Atualiza campos diretos da Filial
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # 3. Atualiza ou Cria as Configurações Satélites
        # Helper interno para evitar repetição de código
        def update_nested(model_class, relation_name, data):
            if data is not None:
                # Tenta pegar a config existente (ex: instance.nfe_config)
                config_obj = getattr(instance, relation_name, None)
                if config_obj:
                    # Atualiza existente
                    for attr, value in data.items():
                        setattr(config_obj, attr, value)
                    config_obj.save()
                else:
                    # Cria nova se não existir
                    model_class.objects.create(filial=instance, **data)

        update_nested(FilialNFeConfig, 'nfe_config', nfe_data)
        update_nested(FilialNFCeConfig, 'nfce_config', nfce_data)
        update_nested(FilialFiscalConfig, 'fiscal_config', fiscal_data)

        return instance