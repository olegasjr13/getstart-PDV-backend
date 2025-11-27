from .bairro_models import Bairro
from .logradouro_models import Logradouro
from .municipio_models import Municipio
from .pais_models import Pais
from .uf_models import UF
from .endereco_models import Endereco   

# Importa os modelos para que possam ser acessados diretamente a partir do pacote enderecos.models
__all__ = [
    'Bairro',
    'Logradouro',
    'Municipio',
    'Pais',
    'UF',
    'Endereco',
]