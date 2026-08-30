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

    return render_template(
        'dashboard/dashboard.html',
        user_name=user_name,
        total_membros=metrics["total_membros"],
        total_transferidos=metrics.get("total_transferidos", 0),
        total_inativos=metrics.get("total_inativos", 0),
        total_geral_membros=metrics.get("total_geral_membros", 0),
        total_batizados=metrics["total_batizados"],
        total_dizimistas=metrics["total_dizimistas"],
        total_eventos=metrics["total_eventos"],
        total_visitantes=metrics["total_visitantes"],
        meses_labels=metrics["meses_labels"],
        financeiro_mensal=metrics["financeiro_mensal"],
        financeiro_saidas=metrics["financeiro_saidas"],
        total_entradas=metrics["entradas_mes"],
        total_saidas=metrics["saidas_mes"],
        has_financeiro_data=metrics["has_financeiro_data"],
        proximos_aniversariantes=metrics["proximos_aniversariantes"],
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

