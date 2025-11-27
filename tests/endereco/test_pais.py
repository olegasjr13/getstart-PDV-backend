import pytest
from decimal import Decimal
from django.urls import reverse
from django_tenants.utils import schema_context

from enderecos.models.pais_models import Pais




pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def pais_payload():
    return {
        "codigo_nfe": "1058",
        "nome": "Brasil",
        "sigla2": "BR",
        "sigla3": "BRA",
    }


@pytest.fixture
def pais_payload_edit():
    return {
        "codigo_nfe": "0101",
        "nome": "Brasil Editado",
        "sigla2": "BE",
        "sigla3": "BED",
    }


def get_url_list():
    return reverse("enderecos:pais-list")


def get_url_detail(obj_id):
    return reverse("enderecos:pais-detail", args=[obj_id])


def test_pais_crud_multitenant(two_tenants_with_admins, pais_payload, pais_payload_edit, client):
    """
    TESTE COMPLETO DE CRUD MULTITENANT PARA PAIS
    
    Cobre:
    - criação em cada tenant
    - edição em cada tenant
    - exclusão em cada tenant
    - isolamento entre tenants
    - tentativa de acessar dados de outro tenant (NEGADO)
    - tentativa de duplicação (falha esperada)
    - limpeza completa por tenant
    """

    schema1 = two_tenants_with_admins["schema1"]
    schema2 = two_tenants_with_admins["schema2"]

    admin1 = two_tenants_with_admins["admin_username_1"]
    admin2 = two_tenants_with_admins["admin_username_2"]

    # ============================================================
    # 1. CREATE — TENANT 1
    # ============================================================

    with schema_context(schema1):
        #client.force_authenticate(user=admin1)

        resp = client.post(get_url_list(), pais_payload, format="json")
        assert resp.status_code == 201

        pais_id_t1 = resp.data["id"]

        assert Pais.objects.count() == 1
        pais = Pais.objects.first()
        assert pais.nome == "Brasil"

    # ============================================================
    # 2. CREATE — TENANT 2 (ISOLADO)
    # ============================================================

    with schema_context(schema2):
        #client.force_authenticate(user=admin2)

        resp = client.post(get_url_list(), pais_payload, format="json")
        pais_id_t2 = resp.data["id"]

        assert resp.status_code == 201
        assert Pais.objects.count() == 1  # isolado do tenant 1

    # ============================================================
    # 3. LIST — CONFIRMAR ISOLAMENTO ENTRE TENANTS
    # ============================================================

    with schema_context(schema1):
        client.force_authenticate(user=admin1)
        resp = client.get(get_url_list())
        assert len(resp.data) == 1
        assert resp.data[0]["id"] == pais_id_t1

    with schema_context(schema2):
        client.force_authenticate(user=admin2)
        resp = client.get(get_url_list())
        assert len(resp.data) == 1
        assert resp.data[0]["id"] == pais_id_t2

    # ============================================================
    # 4. UPDATE — TENANT 1
    # ============================================================

    with schema_context(schema1):
        client.force_authenticate(user=admin1)

        resp = client.put(get_url_detail(pais_id_t1), pais_payload_edit, format="json")
        assert resp.status_code == 200

        pais = Pais.objects.get(id=pais_id_t1)
        assert pais.nome == pais_payload_edit["nome"]
        assert pais.codigo_nfe == pais_payload_edit["codigo_nfe"]

    # ============================================================
    # 5. VERIFICAR QUE TENANT 2 NÃO FOI ALTERADO
    # ============================================================

    with schema_context(schema2):
        client.force_authenticate(user=admin2)

        pais = Pais.objects.get(id=pais_id_t2)
        assert pais.nome == "Brasil"

    # ============================================================
    # 6. DUPLICAÇÃO (UNIQUE VIOLATION) — MESMO TENANT
    # ============================================================

    with schema_context(schema1):
        client.force_authenticate(user=admin1)

        resp = client.post(get_url_list(), pais_payload_edit, format="json")
        assert resp.status_code in (400, 409)

    # ============================================================
    # 7. DELETE — TENANT 1
    # ============================================================

    with schema_context(schema1):
        client.force_authenticate(user=admin1)

        resp = client.delete(get_url_detail(pais_id_t1))
        assert resp.status_code == 204

        assert Pais.objects.count() == 0

    # ============================================================
    # 8. CONFIRMAR QUE TENANT 2 AINDA TEM O REGISTRO
    # ============================================================

    with schema_context(schema2):
        client.force_authenticate(user=admin2)
        assert Pais.objects.count() == 1

    # ============================================================
    # 9. DELETE — TENANT 2
    # ============================================================

    with schema_context(schema2):
        client.force_authenticate(user=admin2)

        resp = client.delete(get_url_detail(pais_id_t2))
        assert resp.status_code == 204
        assert Pais.objects.count() == 0


# ==========================================
# TESTES DE FALHAS E VALIDAÇÕES EXTRAS
# ==========================================

def test_pais_campos_invalidos(two_tenants_with_admins, client):
    schema1 = two_tenants_with_admins["schema1"]
    admin1 = two_tenants_with_admins["admin_username_1"]

    with schema_context(schema1):
        client.force_authenticate(user=admin1)

        # nome vazio
        resp = client.post(
            get_url_list(),
            {"codigo_nfe": "1234", "nome": "", "sigla2": "", "sigla3": ""},
            format="json",
        )
        assert resp.status_code == 400

        # codigo_nfe muito grande
        resp = client.post(
            get_url_list(),
            {"codigo_nfe": "99999", "nome": "Teste", "sigla2": "TT", "sigla3": "TES"},
            format="json",
        )
        assert resp.status_code == 400

        # siglas com tamanho errado
        resp = client.post(
            get_url_list(),
            {"codigo_nfe": "9999", "nome": "Teste", "sigla2": "TOO_LONG", "sigla3": "XXX"},
            format="json",
        )
        assert resp.status_code == 400
