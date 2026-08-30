from datetime import datetime
from sqlalchemy import func
from app.extensions import db
from app.models import Member, Evento, Financeiro

from utils.dates import get_current_datetime

class DashboardService:
    """
    Serviço corporativo para cálculos, agregações estatísticas e indicadores do Dashboard.
    """
    MESES_PT = {
        1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
        5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
        9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
    }

    @classmethod
    def _dias_para_proximo_aniversario(cls, birth_date, ref_date) -> int:
        """
        Calcula os dias restantes até o próximo aniversário a partir de ref_date
        dentro do ciclo anual contínuo (0 se for hoje, dias restantes este ano,
        ou ciclo do próximo ano para aniversários já ocorridos neste ano).
        """
        if not birth_date:
            return 9999
        if isinstance(birth_date, datetime):
            birth_date = birth_date.date()

        try:
            bday_this_year = birth_date.replace(year=ref_date.year)
        except ValueError:
            # Trata 29 de fevereiro em anos não-bissextos
            bday_this_year = birth_date.replace(year=ref_date.year, day=28)

        if bday_this_year >= ref_date:
            return (bday_this_year - ref_date).days
        else:
            try:
                bday_next_year = birth_date.replace(year=ref_date.year + 1)
            except ValueError:
                bday_next_year = birth_date.replace(year=ref_date.year + 1, day=28)
            return (bday_next_year - ref_date).days

    @classmethod
    def get_proximos_aniversariantes(cls, limit: int = 5, ref_date=None) -> list:
        """
        Retorna os aniversariantes mais próximos da data de referência em ordem cronológica
        cíclica (próximos deste ano -> início do próximo ano -> já passados por último).
        """
        if ref_date is None:
            ref_date = get_current_datetime().date()
        elif isinstance(ref_date, datetime):
            ref_date = ref_date.date()

        membros = (
            Member.query
            .filter(Member.data_nascimento.isnot(None))
            .filter(Member.data_saida.is_(None))
            .filter((Member.status.is_(None)) | (Member.status == "Ativo"))
            .all()
        )

        return sorted(
            membros,
            key=lambda m: (
                cls._dias_para_proximo_aniversario(m.data_nascimento, ref_date),
                m.nome.lower() if m.nome else ""
            )
        )[:limit]

    @classmethod
    def get_dashboard_metrics(cls, is_admin: bool = False) -> dict:
        agora = get_current_datetime()
        mes_atual = agora.month
        ano_atual = agora.year
        mes_nome = cls.MESES_PT.get(mes_atual, "Mês Atual")

        # 1. Contagens gerais (apenas membros ativos da congregação são total_membros)
        total_membros = Member.query.filter(Member.data_saida.is_(None), (Member.status.is_(None)) | (Member.status == "Ativo")).count()
        total_transferidos = Member.query.filter(Member.status == "Transferido").count()
        total_inativos = Member.query.filter((Member.status == "Inativo") | (Member.data_saida.isnot(None))).filter(Member.status != "Transferido").count()
        total_geral_membros = Member.query.count()
        total_batizados = Member.query.filter_by(batizado=True).filter(Member.data_saida.is_(None), (Member.status.is_(None)) | (Member.status == "Ativo")).count() if is_admin else 0
        total_dizimistas = Member.query.filter_by(dizimista=True).filter(Member.data_saida.is_(None), (Member.status.is_(None)) | (Member.status == "Ativo")).count() if is_admin else 0
        total_eventos = Evento.query.count()
        total_visitantes = Member.query.filter_by(visitante=True).count()

        # 2. Próximos aniversariantes (visível operacionalmente e ordenado pelo ciclo anual)
        proximos_aniversariantes = cls.get_proximos_aniversariantes(limit=5, ref_date=agora.date())

        # 3. Métricas protegidas e restritas (Apenas para Administrador)
        if not is_admin:
            return {
                "total_membros": total_membros,
                "total_transferidos": total_transferidos,
                "total_inativos": total_inativos,
                "total_geral_membros": total_geral_membros,
                "total_batizados": 0,
                "total_dizimistas": 0,
                "total_eventos": total_eventos,
                "total_visitantes": total_visitantes,
                "entradas_mes": 0.0,
                "saidas_mes": 0.0,
                "meses_labels": [],
                "financeiro_mensal": [],
                "financeiro_saidas": [],
                "has_financeiro_data": False,
                "proximos_aniversariantes": proximos_aniversariantes,
                "crescimento_labels": [],
                "crescimento_valores": [],
                "crescimento_valores_por_ano": {},
                "saidas_valores_por_ano": {},
                "indicadores_por_ano": {},
                "taxa_crescimento": None,
                "tendencia": None,
                "mes_nome": mes_nome
            }

        # 4. Entradas e Saídas do mês (Administrador)
        entradas_mes = (
            db.session.query(func.sum(Financeiro.valor))
            .filter(Financeiro.tipo == "Entrada")
            .filter(func.extract('month', Financeiro.data) == mes_atual)
            .filter(func.extract('year', Financeiro.data) == ano_atual)
            .scalar()
        ) or 0.0

        saidas_mes = (
            db.session.query(func.sum(Financeiro.valor))
            .filter(Financeiro.tipo == "Saída")
            .filter(func.extract('month', Financeiro.data) == mes_atual)
            .filter(func.extract('year', Financeiro.data) == ano_atual)
            .scalar()
        ) or 0.0

        # 3. Histórico dos últimos 6 meses
        entradas_query = (
            db.session.query(
                func.extract('year', Financeiro.data).label("ano"),
                func.extract('month', Financeiro.data).label("mes"),
                func.sum(Financeiro.valor).label("total")
            )
            .filter(Financeiro.tipo == "Entrada")
            .group_by("ano", "mes")
            .order_by("ano", "mes")
            .limit(6)
            .all()
        )
        meses_labels = [
            f"{int(r.mes):02d}/{int(r.ano)}"
            for r in entradas_query if r.mes is not None and r.ano is not None
        ]
        financeiro_mensal = [float(r.total) for r in entradas_query]

        saidas_query = (
            db.session.query(
                func.extract('year', Financeiro.data).label("ano"),
                func.extract('month', Financeiro.data).label("mes"),
                func.sum(Financeiro.valor).label("total")
            )
            .filter(Financeiro.tipo == "Saída")
            .group_by("ano", "mes")
            .order_by("ano", "mes")
            .limit(6)
            .all()
        )
        financeiro_saidas = [float(r.total) for r in saidas_query]
        has_financeiro_data = bool(financeiro_mensal or financeiro_saidas)


        # 5. Crescimento e movimentação anual
        crescimento_query = (
            db.session.query(
                func.extract('year', Member.data_cadastro).label("ano"),
                func.extract('month', Member.data_cadastro).label("mes"),
                func.count(Member.id).label("novos")
            )
            .filter(Member.data_cadastro.isnot(None))
            .group_by("ano", "mes")
            .order_by("ano", "mes")
            .all()
        )
        crescimento_labels = [
            f"{int(r.mes):02d}/{int(r.ano)}"
            for r in crescimento_query if r.mes is not None and r.ano is not None
        ]
        crescimento_valores = [
            int(r.novos)
            for r in crescimento_query if r.mes is not None and r.ano is not None
        ]

        crescimento_valores_por_ano = {}
        for r in crescimento_query:
            if r.ano and r.mes:
                ano = int(r.ano)
                mes = int(r.mes)
                if ano not in crescimento_valores_por_ano:
                    crescimento_valores_por_ano[ano] = [0] * 12
                crescimento_valores_por_ano[ano][mes - 1] = int(r.novos)

        saidas_valores_por_ano = {}
        saidas_membros_query = (
            db.session.query(
                func.extract('year', Member.data_saida).label("ano"),
                func.extract('month', Member.data_saida).label("mes"),
                func.count(Member.id).label("saidas")
            )
            .filter(Member.data_saida.isnot(None))
            .group_by("ano", "mes")
            .order_by("ano", "mes")
            .all()
        )
        for r in saidas_membros_query:
            if r.ano and r.mes:
                ano = int(r.ano)
                mes = int(r.mes)
                if ano not in saidas_valores_por_ano:
                    saidas_valores_por_ano[ano] = [0] * 12
                saidas_valores_por_ano[ano][mes - 1] = int(r.saidas)

        indicadores_por_ano = {}
        anos = db.session.query(func.extract('year', Member.data_cadastro)).distinct().all()
        for (ano,) in anos:
            if ano is None:
                continue
            ano = int(ano)
            entradas_count = (
                db.session.query(func.count(Member.id))
                .filter(func.extract('year', Member.data_cadastro) == ano)
                .scalar()
            ) or 0

            saidas_count = (
                db.session.query(func.count(Member.id))
                .filter(func.extract('year', Member.data_saida) == ano)
                .scalar()
            ) or 0

            movimentacao = entradas_count - saidas_count
            taxa = round((movimentacao / total_membros) * 100, 1) if total_membros > 0 else None

            total_ano = (
                db.session.query(func.count(Member.id))
                .filter(func.extract('year', Member.data_cadastro) <= ano)
                .filter((Member.data_saida.is_(None)) | (func.extract('year', Member.data_saida) > ano))
                .filter((Member.status.is_(None)) | (Member.status == "Ativo"))
                .scalar()
            ) or 0

            indicadores_por_ano[ano] = {
                "entradas": int(entradas_count),
                "saidas": int(saidas_count),
                "movimentacao": int(movimentacao),
                "taxa": float(taxa) if taxa is not None else None,
                "total_membros": int(total_ano)
            }

        taxa_crescimento = None
        tendencia = None
        if len(crescimento_valores) >= 2:
            ultimo = crescimento_valores[-1]
            anterior = crescimento_valores[-2]
            if anterior > 0:
                taxa_crescimento = round(((ultimo - anterior) / anterior) * 100, 1)
                tendencia = "up" if taxa_crescimento > 0 else "down"

        return {
            "total_membros": total_membros,
            "total_transferidos": total_transferidos,
            "total_inativos": total_inativos,
            "total_geral_membros": total_geral_membros,
            "total_batizados": total_batizados,
            "total_dizimistas": total_dizimistas,
            "total_eventos": total_eventos,
            "total_visitantes": total_visitantes,
            "entradas_mes": entradas_mes,
            "saidas_mes": saidas_mes,
            "meses_labels": meses_labels,
            "financeiro_mensal": financeiro_mensal,
            "financeiro_saidas": financeiro_saidas,
            "has_financeiro_data": has_financeiro_data,
            "proximos_aniversariantes": proximos_aniversariantes,
            "crescimento_labels": crescimento_labels,
            "crescimento_valores": crescimento_valores,
            "crescimento_valores_por_ano": crescimento_valores_por_ano,
            "saidas_valores_por_ano": saidas_valores_por_ano,
            "indicadores_por_ano": indicadores_por_ano,
            "taxa_crescimento": taxa_crescimento,
            "tendencia": tendencia,
            "mes_nome": mes_nome
        }
