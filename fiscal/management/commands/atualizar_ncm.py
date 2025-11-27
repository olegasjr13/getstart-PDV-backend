import json
from contextlib import nullcontext
from datetime import datetime
from typing import Any, Dict, Iterable, Optional, Tuple

import requests
from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django_tenants.utils import schema_context


NCM_URL_PADRAO = (
    "https://portalunico.siscomex.gov.br/classif/api/publico/"
    "nomenclatura/download/json?perfil=PUBLICO"
)


def _parse_date(value: Optional[str]) -> Optional[datetime.date]:
    """
    Converte datas do JSON (normalmente 'YYYY-MM-DD') em date().
    Retorna None se vier vazio/nulo.
    """
    if not value:
        return None
    value = value.strip()
    if not value:
        return None

    # Tenta ISO direto
    try:
        # Corta só os 10 primeiros caracteres caso venha com hora.
        return datetime.fromisoformat(value[:10]).date()
    except ValueError:
        # Último fallback: tenta formatos mais comuns
        for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
    return None


def _extrair_itens_ncm(payload: Dict[str, Any]) -> Tuple[Iterable[Dict[str, Any]], Optional[str]]:
    """
    Extrai a lista de itens de NCM e a data de última alteração do JSON.

    Estrutura esperada (varia só em maiúsculas/minúsculas):

    {
        "dataUltimaAlteracao": "2024-10-01",
        "nomenclaturas": [
            {
                "codigo": "01012100",
                "descricao": "Cavalos reprodutores...",
                "dataInicio": "2017-01-01",
                "dataFim": null,
                "tipoOrgaoAtoIni": "...",
                "numeroAtoIni": "...",
                "anoAtoIni": "2016"
            },
            ...
        ]
    }
    """
    # Data de última alteração (útil para versao_tabela)
    data_ultima_alt = (
        payload.get("dataUltimaAlteracao")
        or payload.get("DataUltimaAlteracao")
        or None
    )

    # Lista de nomenclaturas
    itens = (
        payload.get("nomenclaturas")
        or payload.get("Nomenclaturas")
        or payload.get("itens")
        or payload.get("Itens")
    )

    if itens is None:
        # Em último caso, se o payload já for uma lista
        if isinstance(payload, list):
            itens = payload
        else:
            raise CommandError(
                "JSON retornado pelo Siscomex não possui chave "
                "'nomenclaturas'/'Nomenclaturas' nem é uma lista."
            )

    if not isinstance(itens, (list, tuple)):
        raise CommandError("Estrutura de itens NCM inesperada no JSON do Siscomex.")

    return itens, data_ultima_alt


class Command(BaseCommand):
    help = (
        "Atualiza a tabela de NCM a partir do JSON público do "
        "Portal Único Siscomex/Receita Federal."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--url",
            type=str,
            default=NCM_URL_PADRAO,
            help="URL do JSON de NCM (default = URL oficial Siscomex pública).",
        )
        parser.add_argument(
            "--schema-name",
            type=str,
            default=None,
            help=(
                "Nome do schema do tenant onde a tabela fiscal_ncm está. "
                "Se não informado, usa o schema atual (normalmente 'public')."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simula a execução sem gravar no banco.",
        )
        parser.add_argument(
            "--nao-inativar-faltantes",
            action="store_true",
            help=(
                "Não marcar como inativos os NCM que não estiverem presentes "
                "no JSON retornado."
            ),
        )

    def handle(self, *args, **options):
        url = options["url"]
        schema_name = options["schema_name"]
        dry_run = options["dry_run"]
        nao_inativar_faltantes = options["nao_inativar_faltantes"]

        self.stdout.write(self.style.NOTICE(f"[atualizar_ncm] Baixando JSON de: {url}"))

        try:
            resp = requests.get(url, timeout=60)
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise CommandError(f"Erro ao requisitar JSON de NCM: {exc}") from exc

        try:
            payload = resp.json()
        except json.JSONDecodeError as exc:
            raise CommandError(f"Resposta não é um JSON válido: {exc}") from exc

        itens, data_ultima_alt = _extrair_itens_ncm(payload)

        NCM = apps.get_model("fiscal", "NCM")

        self.stdout.write(
            self.style.NOTICE(
                f"[atualizar_ncm] Iniciando processamento de {len(itens)} registros de NCM."
            )
        )

        created = 0
        updated = 0
        unchanged = 0
        inativados = 0

        versao_tabela = None
        if data_ultima_alt:
            versao_tabela = f"NCM-{data_ultima_alt}"

        # Se schema_name foi informado, usamos schema_context; senão, nullcontext
        ctx = schema_context(schema_name) if schema_name else nullcontext()

        with ctx:
            # Para marcar o que veio no JSON
            codigos_recebidos = set()

            # Para lookups rápidos dentro do schema correto
            existentes = {n.codigo: n for n in NCM.objects.all()}

            # Transação única dentro do schema alvo
            with transaction.atomic():
                for raw in itens:
                    # Campos podem vir com caixa alta/baixa
                    codigo = (raw.get("codigo") or raw.get("Codigo") or "").strip()
                    if not codigo:
                        # ignora linhas sem código
                        continue

                    descricao = (raw.get("descricao") or raw.get("Descricao") or "").strip()

                    data_inicio = _parse_date(
                        raw.get("dataInicio") or raw.get("DataInicio")
                    )
                    data_fim = _parse_date(
                        raw.get("dataFim") or raw.get("DataFim")
                    )

                    tipo_orgao = raw.get("tipoOrgaoAtoIni") or raw.get("TipoOrgaoAtoIni")
                    numero_ato = raw.get("numeroAtoIni") or raw.get("NumeroAtoIni")
                    ano_ato = raw.get("anoAtoIni") or raw.get("AnoAtoIni")

                    observacoes_parts = []
                    if tipo_orgao or numero_ato or ano_ato:
                        observacoes_parts.append("Ato legal de criação/alteração:")
                        if tipo_orgao:
                            observacoes_parts.append(f"Órgão: {tipo_orgao}")
                        if numero_ato:
                            observacoes_parts.append(f"Nº: {numero_ato}")
                        if ano_ato:
                            observacoes_parts.append(f"Ano: {ano_ato}")

                    observacoes = " | ".join(observacoes_parts)

                    codigos_recebidos.add(codigo)

                    defaults = {
                        "descricao": descricao,
                        "vigencia_inicio": data_inicio,
                        "vigencia_fim": data_fim,
                        "versao_tabela": versao_tabela or "",
                        "observacoes": observacoes,
                        "ativo": True,
                    }

                    ncm_existente = existentes.get(codigo)

                    if ncm_existente is None:
                        if not dry_run:
                            NCM.objects.create(
                                codigo=codigo,
                                **defaults,
                            )
                        created += 1
                    else:
                        mudou = False
                        for campo, novo_valor in defaults.items():
                            valor_atual = getattr(ncm_existente, campo)
                            if valor_atual != novo_valor:
                                setattr(ncm_existente, campo, novo_valor)
                                mudou = True
                        if mudou:
                            if not dry_run:
                                ncm_existente.save()
                            updated += 1
                        else:
                            unchanged += 1

                # Inativar NCM que existem no banco mas não vieram no JSON
                if not nao_inativar_faltantes:
                    hoje = timezone.now().date()
                    qs_faltantes = NCM.objects.filter(ativo=True).exclude(
                        codigo__in=codigos_recebidos
                    )
                    for ncm in qs_faltantes:
                        ncm.ativo = False
                        if not ncm.vigencia_fim:
                            ncm.vigencia_fim = hoje
                        if not dry_run:
                            ncm.save(update_fields=["ativo", "vigencia_fim"])
                        inativados += 1

                if dry_run:
                    # Apenas log informativo: nenhuma escrita foi feita porque
                    # todos os creates/saves estão protegidos por "if not dry_run".
                    self.stdout.write(
                        self.style.WARNING(
                            "[atualizar_ncm] DRY-RUN habilitado: nenhuma alteração foi persistida."
                        )
                    )

        self.stdout.write(
            self.style.SUCCESS(
                "[atualizar_ncm] Concluído. "
                f"Criados: {created}, Atualizados: {updated}, "
                f"Sem mudança: {unchanged}, Inativados: {inativados}."
            )
        )
