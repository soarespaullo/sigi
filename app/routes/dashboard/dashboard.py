from flask import Blueprint, render_template, session, redirect, url_for, flash
from datetime import datetime, timedelta
from flask_login import login_required, current_user
from app.models import Evento
from app.services.dashboard_service import DashboardService

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/dashboard')
@login_required
def dashboard():
    user = current_user
    user_name = user.nome if user.nome else user.email.split('@')[0].capitalize()

    is_admin = getattr(user, "is_admin", False)
    metrics = DashboardService.get_dashboard_metrics(is_admin=is_admin)

    # Checa eventos próximos para disparar notificação
    try:
        agora = datetime.now()
        em_dois_dias = agora + timedelta(days=2)
        existe_evento = (
            Evento.query
            .filter(Evento.data_inicio <= em_dois_dias, Evento.data_fim >= agora)
            .first()
        )
        if existe_evento and not session.get("evento_alert") and not session.get("evento_alert_dismissed"):
            session["evento_alert"] = "⚠️ Há eventos próximos ou em andamento nos próximos 2 dias. Clique aqui para ver todos."
            session["evento_alert_type"] = "warning"
    except Exception:
        pass

    return render_template(
        'dashboard/dashboard.html',
        user_name=user_name,
        total_membros=metrics["total_membros"],
        total_transferidos=metrics.get("total_transferidos", 0),
        total_inativos=metrics.get("total_inativos", 0),
        total_geral_membros=metrics.get("total_geral_membros", 0),
        total_batizados=metrics["total_batizados"],
        nao_batizados_ativos=metrics.get("nao_batizados_ativos", 0),
        total_dizimistas=metrics["total_dizimistas"],
        total_eventos=metrics["total_eventos"],
        total_eventos_programados=metrics.get("total_eventos_programados", 0),
        proximos_eventos=metrics.get("proximos_eventos", []),
        total_visitantes=metrics["total_visitantes"],
        total_escalas=metrics.get("total_escalas", 0),
        proximas_escalas=metrics.get("proximas_escalas", []),
        total_voluntarios_pendentes=metrics.get("total_voluntarios_pendentes", 0),
        membros_novos_mes=metrics.get("membros_novos_mes", 0),
        meses_labels=metrics["meses_labels"],
        financeiro_mensal=metrics["financeiro_mensal"],
        financeiro_saidas=metrics["financeiro_saidas"],
        total_entradas=metrics["entradas_mes"],
        total_saidas=metrics["saidas_mes"],
        saldo_operacional=metrics.get("saldo_operacional", 0.0),
        saldo_acumulado=metrics.get("saldo_acumulado", 0.0),
        has_financeiro_data=metrics["has_financeiro_data"],
        proximos_aniversariantes=metrics["proximos_aniversariantes"],
        aniversariantes_hoje=metrics.get("aniversariantes_hoje", []),
        crescimento_labels=metrics["crescimento_labels"],
        crescimento_valores=metrics["crescimento_valores"],
        crescimento_valores_por_ano=metrics["crescimento_valores_por_ano"],
        saidas_valores_por_ano=metrics["saidas_valores_por_ano"],
        indicadores_por_ano=metrics["indicadores_por_ano"],
        taxa_crescimento=metrics["taxa_crescimento"],
        tendencia=metrics["tendencia"],
        mes_nome=metrics["mes_nome"]
    )

@dashboard_bp.route("/dismiss-evento-alert")
def dismiss_evento_alert():
    session.pop("evento_alert", None)
    session.pop("evento_alert_type", None)
    session["evento_alert_dismissed"] = True
    return "", 204

