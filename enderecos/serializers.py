from rest_framework import serializers
from enderecos.models.pais_models import Pais
from enderecos.models.uf_models import UF
from enderecos.models.municipio_models import Municipio
from enderecos.models.bairro_models import Bairro
from enderecos.models.logradouro_models import Logradouro
from enderecos.models.endereco_models import Endereco

class PaisSerializer(serializers.ModelSerializer):
    class Meta:
        model = Pais
        fields = '__all__' # Expõe todos os campos (id, nome, codigo_nfe...)

class UFSerializer(serializers.ModelSerializer):
    # Para exibição, podemos mostrar o nome do país. 
    # Para escrita, usamos o ID (padrão do DRF).
    pais_nome = serializers.ReadOnlyField(source='pais.nome')

    class Meta:
        model = UF
        fields = ['id', 'sigla', 'nome', 'codigo_ibge', 'pais', 'pais_nome']

class MunicipioSerializer(serializers.ModelSerializer):
    uf_sigla = serializers.ReadOnlyField(source='uf.sigla')

    class Meta:
        model = Municipio
        fields = ['id', 'nome', 'codigo_ibge', 'uf', 'uf_sigla', 'codigo_siafi']
        # Validadores extras podem ser adicionados aqui se necessário, 
        # mas as constraints do model já são verificadas.

class BairroSerializer(serializers.ModelSerializer):
    municipio_nome = serializers.ReadOnlyField(source='municipio.nome')

    class Meta:
        model = Bairro
        fields = ['id', 'nome', 'municipio', 'municipio_nome']

class LogradouroSerializer(serializers.ModelSerializer):
    # Display do tipo (ex: "Avenida" em vez de "AV")
    tipo_display = serializers.CharField(source='get_tipo_display', read_only=True)
    bairro_nome = serializers.ReadOnlyField(source='bairro.nome')

    class Meta:
        model = Logradouro
        fields = ['id', 'tipo', 'tipo_display', 'nome', 'cep', 'bairro', 'bairro_nome']

class EnderecoSerializer(serializers.ModelSerializer):
    """
    Serializer completo para Endereço.
    Inclui os campos auxiliares (properties) para facilitar o frontend/NFe.
    """
    # Campos Read-Only que vêm das properties do Model
    xLgr = serializers.ReadOnlyField()
    xBairro = serializers.ReadOnlyField()
    xMun = serializers.ReadOnlyField()
    uf = serializers.ReadOnlyField()
    xPais = serializers.ReadOnlyField()

    class Meta:
        model = Endereco
        fields = [
            'id', 'logradouro', 'numero', 'complemento', 'cep', 'referencia',
            # Campos calculados (úteis para visualização)
            'xLgr', 'xBairro', 'xMun', 'uf', 'xPais'
        ]