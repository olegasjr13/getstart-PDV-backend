# tenants/views/tenants_views.py

import logging

from django.apps import apps
from django.core.management import call_command
from django.db import connection, IntegrityError
from django.contrib.auth import get_user_model
from django_tenants.utils import get_tenant_model, schema_context
from rest_framework import status
from rest_framework.decorators import (
    api_view,
    permission_classes,
    authentication_classes,
)
from rest_framework.response import Response

from tenants.permissions import PublicProvisioningPermission
from tenants.serializers import TenantCreateSerializer
from usuario.models.usuario_models import UserPerfil

logger = logging.getLogger(__name__)


def _drop_schema_if_exists(schema_name: str) -> None:
    """
    Dropa o schema de um tenant diretamente no PostgreSQL, caso exista.
    """
    connection.set_schema_to_public()
    with connection.cursor() as cursor:
        cursor.execute(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE;')
    logger.info("Schema '%s' dropado (se existia).", schema_name)


def _safe_cleanup_tenant(tenant) -> None:
    """
    Limpa tenant parcialmente provisionado (Domain + schema + Tenant).
    Usado em cenários de erro para não deixar lixo.
    """
    if tenant is None:
        return

    TenantModel = get_tenant_model()
    DomainModel = apps.get_model("tenants", "Domain")

    connection.set_schema_to_public()

    try:
        tenant_db = TenantModel.objects.filter(pk=tenant.pk).first()
        if not tenant_db:
            return

        logger.warning(
            "Fazendo cleanup de tenant '%s' (schema_name=%s) após falha no provisionamento.",
            tenant_db.cnpj_raiz,
            tenant_db.schema_name,
        )

        DomainModel.objects.filter(tenant=tenant_db).delete()
        schema_name = tenant_db.schema_name

        tenant_db.delete()
        _drop_schema_if_exists(schema_name)
    except Exception:
        logger.exception("Erro ao limpar tenant após falha no provisionamento.")


def _criar_usuario_admin_para_filial(filial):
    """
    Cria um usuário ADMIN padrão dentro do schema do tenant, vinculado à filial.

    Boas práticas:
      - Usa get_user_model() para respeitar AUTH_USER_MODEL.
      - Descobre o app_label dinamicamente para buscar UserFilial.
      - Cria usuário com perfil ADMIN, superuser, staff, ativo.
      - Define senha inutilizável (fluxo posterior de definição de senha).
    """
    User = get_user_model()
    user_app_label = User._meta.app_label
    UserFilial = apps.get_model(user_app_label, "UserFilial")

    # username padrão = CNPJ raiz da filial, se disponível via relação, ou o próprio UUID
    username_padrao = str(filial.id)

    # Se sua Filial tiver campo cnpj_raiz ou algo do tipo, pode alterar aqui depois:
    # username_padrao = filial.cnpj_raiz

    perfil = UserPerfil.objects.filter(descricao="ADMIN").first()

    admin_user = User.objects.create(
        username=username_padrao,
        email="",
        perfil=perfil.id if perfil else None,
        is_superuser=True,
        is_staff=True,
        is_active=True,
    )
    # Sem senha utilizável por padrão – fluxo de redefinição depois
    admin_user.set_unusable_password()
    admin_user.save(update_fields=["password"])

    UserFilial.objects.create(
        user=admin_user,
        filial_id=filial.id,
    )

    return admin_user


@api_view(["POST"])
@authentication_classes([])
@permission_classes([PublicProvisioningPermission])
def criar_tenant(request):
    """
    Cria um novo tenant + schema + domínio e,
    DENTRO DO NOVO TENANT, cria:

      - Pais / UF / Município / Bairro / Logradouro (via get_or_create)
      - Endereco
      - Filial inicial (ligada ao Endereco)
      - Usuário ADMIN vinculado à Filial (User + UserFilial)

    Segurança / Robustez:
      - Usa TenantCreateSerializer para validar input (400 em caso de erro).
      - Garante que cnpj_raiz (schema_name) e domain não estejam em uso.
      - Em caso de IntegrityError ou outra falha após criar o schema,
        realiza cleanup (tenant + domain + schema) e retorna resposta segura.
    """
    ser = TenantCreateSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    data = ser.validated_data

    Tenant = get_tenant_model()
    Domain = apps.get_model("tenants", "Domain")

    schema_name = data["cnpj_raiz"]
    domain_name = data["domain"]

    # ------------------------------------------------------------------
    # 0) Checagens prévias de conflito
    # ------------------------------------------------------------------
    connection.set_schema_to_public()

    if Tenant.objects.filter(schema_name=schema_name).exists():
        return Response(
            {
                "detail": "Já existe um tenant provisionado com este CNPJ raiz.",
                "field": "cnpj_raiz",
                "code": "tenant_already_exists",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if Domain.objects.filter(domain=domain_name).exists():
        return Response(
            {
                "detail": "Já existe um domínio provisionado com este valor.",
                "field": "domain",
                "code": "domain_already_exists",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    tenant = None
    filial = None
    admin_user = None

    try:
        # ------------------------------------------------------------------
        # 1) Cria o tenant no schema público
        # ------------------------------------------------------------------
        tenant = Tenant(
            schema_name=schema_name,
            cnpj_raiz=data["cnpj_raiz"],
            nome=data["nome"],
            premium_db_alias=data.get("premium_db_alias") or None,
        )
        tenant.save()  # cria o schema no banco

        # ------------------------------------------------------------------
        # 2) Migra apps do tenant (somente esse schema)
        # ------------------------------------------------------------------
        call_command(
            "migrate_schemas",
            tenant=True,
            schema_name=tenant.schema_name,
            interactive=False,
            verbosity=0,
        )

        # ------------------------------------------------------------------
        # 3) Cria o domínio principal
        # ------------------------------------------------------------------
        Domain.objects.create(
            domain=domain_name,
            tenant=tenant,
            is_primary=True,
        )

        # ------------------------------------------------------------------
        # 4) Dentro do schema do tenant, criar a hierarquia de endereço + filial + admin
        # ------------------------------------------------------------------
        filial_payload = data["filial"]
        endereco_payload = filial_payload["endereco"]

        with schema_context(tenant.schema_name):
            Pais = apps.get_model("enderecos", "Pais")
            UFModel = apps.get_model("enderecos", "UF")
            MunicipioModel = apps.get_model("enderecos", "Municipio")
            BairroModel = apps.get_model("enderecos", "Bairro")
            LogradouroModel = apps.get_model("enderecos", "Logradouro")
            EnderecoModel = apps.get_model("enderecos", "Endereco")
            FilialModel = apps.get_model("filial", "Filial")

            # ----- País -----
            pais_data = endereco_payload["pais"]
            pais, _ = Pais.objects.get_or_create(
                codigo_nfe=pais_data["codigo_nfe"],
                defaults={
                    "nome": pais_data["nome"],
                    "sigla2": pais_data.get("sigla2") or "",
                    "sigla3": pais_data.get("sigla3") or "",
                },
            )

            # ----- UF -----
            uf_data = endereco_payload["uf"]
            uf, _ = UFModel.objects.get_or_create(
                sigla=uf_data["sigla"],
                defaults={
                    "nome": uf_data["nome"],
                    "codigo_ibge": uf_data["codigo_ibge"],
                    "pais": pais,
                },
            )

            # ----- Município -----
            mun_data = endereco_payload["municipio"]
            municipio, _ = MunicipioModel.objects.get_or_create(
                codigo_ibge=mun_data["codigo_ibge"],
                defaults={
                    "nome": mun_data["nome"],
                    "uf": uf,
                    "codigo_siafi": mun_data.get("codigo_siafi") or "",
                },
            )

            # ----- Bairro -----
            bairro_nome = endereco_payload["bairro"]
            bairro, _ = BairroModel.objects.get_or_create(
                nome=bairro_nome,
                municipio=municipio,
            )

            # ----- Logradouro -----
            log_tipo = endereco_payload["logradouro_tipo"]
            log_nome = endereco_payload["logradouro_nome"]
            log_cep = endereco_payload["logradouro_cep"]

            logradouro, _ = LogradouroModel.objects.get_or_create(
                tipo=log_tipo,
                nome=log_nome,
                bairro=bairro,
                defaults={
                    "cep": log_cep,
                },
            )

            # ----- Endereco -----
            endereco = EnderecoModel.objects.create(
                logradouro=logradouro,
                numero=endereco_payload["numero"],
                complemento=endereco_payload.get("complemento") or "",
                referencia=endereco_payload.get("referencia") or "",
                cep=endereco_payload["cep"],
            )

            # ----- Filial -----
            filial = FilialModel.objects.create(
                razao_social=filial_payload["razao_social"],
                nome_fantasia=filial_payload["nome_fantasia"],
                cnpj=filial_payload["cnpj"],
                endereco=endereco,
                ativo=True,
            )

            # ----- Usuário ADMIN vinculado à filial -----
            admin_user = _criar_usuario_admin_para_filial(filial)

    except IntegrityError:
        logger.exception("Erro de integridade ao provisionar tenant '%s'.", schema_name)
        _safe_cleanup_tenant(tenant)
        return Response(
            {
                "detail": "Não foi possível provisionar o tenant devido a um "
                          "conflito de dados (integridade).",
                "code": "integrity_error",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    except Exception:
        logger.exception("Erro inesperado ao provisionar tenant '%s'.", schema_name)
        _safe_cleanup_tenant(tenant)
        return Response(
            {
                "detail": "Ocorreu um erro interno ao provisionar o tenant.",
                "code": "unexpected_error",
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # ------------------------------------------------------------------
    # Sucesso
    # ------------------------------------------------------------------
    return Response(
        {
            "tenant": tenant.cnpj_raiz,
            "schema": tenant.schema_name,
            "domain": domain_name,
            "filial_id": str(filial.id),
            "admin_user_id": str(admin_user.id) if admin_user else None,
            "admin_username": admin_user.username if admin_user else None,
        },
        status=status.HTTP_201_CREATED,
    )
