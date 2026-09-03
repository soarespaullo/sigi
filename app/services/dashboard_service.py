from datetime import datetime
from sqlalchemy import func
from app.extensions import db
from app.models import Member, Evento, Financeiro, Escala, EscalaItem

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
        total_membros = Member.query.filter((Member.status.is_(None)) | (Member.status == "Ativo")).count()
        total_transferidos = Member.query.filter(Member.status == "Transferido").count()
        total_inativos = Member.query.filter(Member.status == "Inativo").count()
        total_geral_membros = Member.query.count()
        total_batizados = Member.query.filter_by(batizado=True).filter((Member.status.is_(None)) | (Member.status == "Ativo")).count() if is_admin else 0
        total_dizimistas = Member.query.filter_by(dizimista=True).filter((Member.status.is_(None)) | (Member.status == "Ativo")).count() if is_admin else 0
        total_eventos = Evento.query.count()
        total_visitantes = Member.query.filter_by(visitante=True).count()
        # Próximas escalas e voluntários (defensivo caso tabelas sejam novas no servidor)
        try:
            total_escalas = Escala.query.filter(Escala.status != "cancelada").count()
            proximas_escalas = (
                Escala.query
                .filter(Escala.data >= agora.date(), Escala.status != "cancelada")
                .order_by(Escala.data.asc(), Escala.hora_inicio.asc())
                .limit(4)
                .all()
            )
            total_voluntarios_pendentes = (
                db.session.query(func.count(EscalaItem.id))
                .join(Escala, EscalaItem.escala_id == Escala.id)
                .filter(
                    Escala.data >= agora.date(),
                    Escala.status != "cancelada",
                    EscalaItem.status == "pendente"
                )
                .scalar()
            ) or 0
        except Exception:
            total_escalas = 0
            proximas_escalas = []
            total_voluntarios_pendentes = 0

        # Novos membros cadastrados no mês corrente
        try:
            membros_novos_mes = (
                Member.query
                .filter(
                    Member.data_cadastro.isnot(None),
                    func.extract('month', Member.data_cadastro) == mes_atual,
                    func.extract('year', Member.data_cadastro) == ano_atual
                )
                .count()
            )
        except Exception:
            membros_novos_mes = 0

        # Eventos programados futuros reais
        try:
            total_eventos_programados = (
                Evento.query
                .filter(Evento.data_fim >= agora, Evento.status != "cancelado")
                .count()
            )
            proximos_eventos = (
                Evento.query
                .filter(Evento.data_fim >= agora, Evento.status != "cancelado")
                .order_by(Evento.data_inicio.asc())
                .limit(3)
                .all()
            )
        except Exception:
            total_eventos_programados = 0
            proximos_eventos = []

        # 2. Próximos aniversariantes
        proximos_aniversariantes = cls.get_proximos_aniversariantes(limit=6, ref_date=agora.date())
        aniversariantes_hoje = [
            m for m in proximos_aniversariantes
            if m.data_nascimento and m.data_nascimento.day == agora.day and m.data_nascimento.month == agora.month
        ]
        nao_batizados_ativos = max(total_membros - total_batizados, 0)

        # 3. Métricas protegidas e restritas (Apenas para Administrador)
        if not is_admin:
            return {
                "total_membros": total_membros,
                "total_transferidos": total_transferidos,
                "total_inativos": total_inativos,
                "total_geral_membros": total_geral_membros,
                "total_batizados": 0,
                "nao_batizados_ativos": 0,
                "total_dizimistas": 0,
                "total_eventos": total_eventos,
                "total_eventos_programados": total_eventos_programados,
                "proximos_eventos": proximos_eventos,
                "total_visitantes": total_visitantes,
                "total_escalas": total_escalas,
                "proximas_escalas": proximas_escalas,
                "total_voluntarios_pendentes": total_voluntarios_pendentes,
                "membros_novos_mes": membros_novos_mes,
                "entradas_mes": 0.0,
                "saidas_mes": 0.0,
                "saldo_operacional": 0.0,
                "saldo_acumulado": 0.0,
                "meses_labels": [],
                "financeiro_mensal": [],
                "financeiro_saidas": [],
                "has_financeiro_data": False,
                "proximos_aniversariantes": proximos_aniversariantes,
                "aniversariantes_hoje": aniversariantes_hoje,
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

        # Saldo consolidado acumulado em contas de caixa/banco
        total_entradas_geral = (
            db.session.query(func.sum(Financeiro.valor))
            .filter(Financeiro.tipo == "Entrada")
            .scalar()
        ) or 0.0
        total_saidas_geral = (
            db.session.query(func.sum(Financeiro.valor))
            .filter(Financeiro.tipo == "Saída")
            .scalar()
        ) or 0.0
        saldo_acumulado = float(total_entradas_geral - total_saidas_geral)
        saldo_operacional = float(entradas_mes - saidas_mes)

        # 3. Histórico dos últimos 6 meses cronológicos reais
        ano_col = func.extract('year', Financeiro.data)
        mes_col = func.extract('month', Financeiro.data)
        try:
            periodos_query = (
                db.session.query(
                    ano_col.label("ano"),
                    mes_col.label("mes")
                )
                .filter(Financeiro.data.isnot(None))
                .group_by(ano_col, mes_col)
                .order_by(ano_col.desc(), mes_col.desc())
                .limit(6)
                .all()
            )
            periodos = list(reversed(periodos_query))
            meses_labels = [
                f"{int(p.mes):02d}/{int(p.ano)}"
                for p in periodos if p.ano and p.mes
            ]

            entradas_agrupadas = {
                (int(r.ano), int(r.mes)): float(r.total)
                for r in db.session.query(
                    ano_col.label("ano"),
                    mes_col.label("mes"),
                    func.sum(Financeiro.valor).label("total")
                )
                .filter(Financeiro.tipo == "Entrada", Financeiro.data.isnot(None))
                .group_by(ano_col, mes_col)
                .all()
                if r.ano and r.mes
            }

            saidas_agrupadas = {
                (int(r.ano), int(r.mes)): float(r.total)
                for r in db.session.query(
                    ano_col.label("ano"),
                    mes_col.label("mes"),
                    func.sum(Financeiro.valor).label("total")
                )
                .filter(Financeiro.tipo == "Saída", Financeiro.data.isnot(None))
                .group_by(ano_col, mes_col)
                .all()
                if r.ano and r.mes
            }

            financeiro_mensal = [entradas_agrupadas.get((int(p.ano), int(p.mes)), 0.0) for p in periodos if p.ano and p.mes]
            financeiro_saidas = [saidas_agrupadas.get((int(p.ano), int(p.mes)), 0.0) for p in periodos if p.ano and p.mes]
            has_financeiro_data = bool(financeiro_mensal or financeiro_saidas)
        except Exception:
            meses_labels = []
            financeiro_mensal = []
            financeiro_saidas = []
            has_financeiro_data = False

        # 5. Crescimento e movimentação anual
        crescimento_labels = []
        crescimento_valores = []
        crescimento_valores_por_ano = {}
        saidas_valores_por_ano = {}
        indicadores_por_ano = {}

        try:
            m_ano_col = func.extract('year', Member.data_cadastro)
            m_mes_col = func.extract('month', Member.data_cadastro)
            crescimento_query = (
                db.session.query(
                    m_ano_col.label("ano"),
                    m_mes_col.label("mes"),
                    func.count(Member.id).label("novos")
                )
                .filter(Member.data_cadastro.isnot(None))
                .group_by(m_ano_col, m_mes_col)
                .order_by(m_ano_col.asc(), m_mes_col.asc())
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

            for r in crescimento_query:
                if r.ano and r.mes:
                    ano = int(r.ano)
                    mes = int(r.mes)
                    if ano not in crescimento_valores_por_ano:
                        crescimento_valores_por_ano[ano] = [0] * 12
                    crescimento_valores_por_ano[ano][mes - 1] = int(r.novos)

            s_ano_col = func.extract('year', Member.data_saida)
            s_mes_col = func.extract('month', Member.data_saida)
            saidas_membros_query = (
                db.session.query(
                    s_ano_col.label("ano"),
                    s_mes_col.label("mes"),
                    func.count(Member.id).label("saidas")
                )
                .filter(Member.data_saida.isnot(None))
                .group_by(s_ano_col, s_mes_col)
                .order_by(s_ano_col.asc(), s_mes_col.asc())
                .all()
            )
            for r in saidas_membros_query:
                if r.ano and r.mes:
                    ano = int(r.ano)
                    mes = int(r.mes)
                    if ano not in saidas_valores_por_ano:
                        saidas_valores_por_ano[ano] = [0] * 12
                    saidas_valores_por_ano[ano][mes - 1] = int(r.saidas)

            anos = db.session.query(m_ano_col).distinct().all()
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
        except Exception:
            pass

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
            "nao_batizados_ativos": nao_batizados_ativos,
            "total_dizimistas": total_dizimistas,
            "total_eventos": total_eventos,
            "total_eventos_programados": total_eventos_programados,
            "proximos_eventos": proximos_eventos,
            "total_visitantes": total_visitantes,
            "total_escalas": total_escalas,
            "proximas_escalas": proximas_escalas,
            "total_voluntarios_pendentes": total_voluntarios_pendentes,
            "membros_novos_mes": membros_novos_mes,
            "entradas_mes": entradas_mes,
            "saidas_mes": saidas_mes,
            "saldo_operacional": saldo_operacional,
            "saldo_acumulado": saldo_acumulado,
            "meses_labels": meses_labels,
            "financeiro_mensal": financeiro_mensal,
            "financeiro_saidas": financeiro_saidas,
            "has_financeiro_data": has_financeiro_data,
            "proximos_aniversariantes": proximos_aniversariantes,
            "aniversariantes_hoje": aniversariantes_hoje,
            "crescimento_labels": crescimento_labels,
            "crescimento_valores": crescimento_valores,
            "crescimento_valores_por_ano": crescimento_valores_por_ano,
            "saidas_valores_por_ano": saidas_valores_por_ano,
            "indicadores_por_ano": indicadores_por_ano,
            "taxa_crescimento": taxa_crescimento,
            "tendencia": tendencia,
            "mes_nome": mes_nome
        }
