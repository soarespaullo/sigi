from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, jsonify
from flask_mail import Message
from datetime import datetime, timedelta
from app.extensions import db, mail              # ✅ importa db e mail da extensions.py
from app.models import Evento, Member, User      # ✅ importa models do pacote app.models
from app.routes.event.forms import EventoForm    # ✅ ajusta para app.routes
from flask_login import login_required, current_user   # 👈 protege rotas com Flask-Login
from utils.logs import registrar_log             # 👈 importa função de log
from app.decorators import permission_required   # 🔹 importa o decorator
from app.models.permissions_helper import has_permission
from utils.sanitizer import sanitizar_html

event_bp = Blueprint("event", __name__, url_prefix="/eventos")

# -----------------------------
# 📋 Listar eventos com paginação
# -----------------------------
@event_bp.route("/", methods=["GET"])
@login_required
@permission_required("eventos", "view")
def listar_eventos():
    page = request.args.get("page", 1, type=int)
    eventos = Evento.query.order_by(*Evento.get_order_by_proximos_e_passados()).paginate(page=page, per_page=10)
    return render_template("eventos/listar_eventos.html", eventos=eventos)
    

# -----------------------------
# ➕ Criar novo evento
# -----------------------------
@event_bp.route("/novo", methods=["GET", "POST"])
@login_required
@permission_required("eventos", "create")
def novo_evento():
    form = EventoForm()
    if form.validate_on_submit():
        evento = Evento(
            titulo=form.titulo.data,
            descricao=sanitizar_html(form.descricao.data),
            tipo=form.tipo.data,
            data_inicio=form.data_inicio.data,
            data_fim=form.data_fim.data,
            local=form.local.data,
            organizador=form.organizador.data,
            status=form.status.data
        )
        evento.token_expira_em = evento.data_fim
        db.session.add(evento)
        db.session.commit()
        registrar_log(current_user.nome, f"Criou evento: {evento.titulo}", "sucesso")
        flash(f"Evento {evento.titulo} criado com sucesso!", "success")
        return redirect(url_for("event.listar_eventos"))
    return render_template("eventos/novo_evento.html", form=form)

# -----------------------------
# ✏️ Editar evento
# -----------------------------
@event_bp.route("/editar/<int:id>", methods=["GET", "POST"])
@login_required
@permission_required("eventos", "edit")
def editar_evento(id):
    evento = Evento.query.get_or_404(id)
    form = EventoForm(obj=evento)
    if form.validate_on_submit():
        evento.titulo = form.titulo.data
        evento.descricao = sanitizar_html(form.descricao.data)
        evento.tipo = form.tipo.data
        evento.data_inicio = form.data_inicio.data
        evento.data_fim = form.data_fim.data
        evento.local = form.local.data
        evento.organizador = form.organizador.data
        evento.status = form.status.data

        if evento.status in ["concluido", "cancelado", "concluído"]:
            evento.token_expira_em = datetime.utcnow()
        else:
            evento.token_expira_em = evento.data_fim

        db.session.commit()
        registrar_log(current_user.nome, f"Editou evento: {evento.titulo}", "sucesso")
        flash(f"Evento {evento.titulo} atualizado com sucesso!", "success")
        return redirect(url_for("event.listar_eventos"))
    return render_template("eventos/editar_evento.html", form=form, evento=evento)

# -----------------------------
# ❌ Excluir evento
# -----------------------------
@event_bp.route("/excluir/<int:id>", methods=["POST"])
@login_required
@permission_required("eventos", "delete")
def excluir_evento(id):
    evento = Evento.query.get_or_404(id)
    db.session.delete(evento)
    db.session.commit()
    registrar_log(current_user.nome, f"Excluiu evento: {evento.titulo}", "sucesso")
    flash(f"Evento {evento.titulo} excluído com sucesso!", "danger")
    return redirect(url_for("event.listar_eventos"))

# -----------------------------
# 🔍 Buscar Eventos com paginação
# -----------------------------
@event_bp.route("/buscar", methods=["GET"])
@login_required
@permission_required("eventos", "view")
def buscar_eventos():
    termo = request.args.get("q", "").strip().lower()
    page = request.args.get("page", 1, type=int)

    query = Evento.query
    if termo:
        query = query.filter(
            (Evento.titulo.ilike(f"%{termo}%")) |
            (Evento.tipo.ilike(f"%{termo}%")) |
            (Evento.organizador.ilike(f"%{termo}%"))
        )

    query = query.order_by(*Evento.get_order_by_proximos_e_passados())
    eventos = query.paginate(page=page, per_page=10)

    if termo:
        if eventos.total == 0:
            flash("Nenhum evento corresponde ao termo pesquisado", "warning")
        elif eventos.total == 1:
            flash("1 evento encontrado", "info")
        else:
            flash(f"{eventos.total} evento(s) encontrados", "info")

    return render_template("eventos/listar_eventos.html", eventos=eventos, termo=termo)


# -----------------------------
# 📧 Enviar lembretes de eventos próximos
# -----------------------------
@event_bp.route("/enviar-lembretes", methods=["GET"])
@login_required
@permission_required("eventos", "edit")
def enviar_lembretes_eventos():
    hoje = datetime.now()
    limite = hoje + timedelta(days=3)

    eventos = Evento.query.filter(
        Evento.data_inicio >= hoje,
        Evento.data_inicio <= limite
    ).all()

    if not eventos:
        flash("Nenhum evento próximo para enviar lembrete.", "info")
        return redirect(url_for("event.listar_eventos"))

    member_emails = [m.email.strip() for m in Member.query.filter(Member.email != None).all() if m.email and m.email.strip()]
    admin = User.query.filter_by(is_admin=True).first()
    admin_email = admin.email if admin else None

    recipients = member_emails
    if admin_email and admin_email not in recipients:
        recipients.append(admin_email)

    if not recipients:
        flash("Nenhum destinatário de e-mail encontrado para envio.", "warning")
        return redirect(url_for("event.listar_eventos"))

    enviados = 0
    for ev in eventos:
        try:
            html_body = render_template("email/lembrete_evento.html", evento=ev)
            msg = Message(
                subject=f"Lembrete: {ev.titulo} está chegando!",
                recipients=recipients,
                html=html_body
            )
            mail.send(msg)
            registrar_log(current_user.nome, f"Enviou lembrete do evento: {ev.titulo}", "sucesso")
            enviados += 1
        except Exception as e:
            registrar_log(current_user.nome, f"Erro ao enviar lembrete do evento {ev.titulo}: {e}", "erro")

    if enviados > 0:
        flash(f"Lembretes enviados com sucesso para {enviados} evento(s)!", "success")
    else:
        flash("Ocorreu um erro ao tentar enviar os e-mails de lembrete.", "danger")
    return redirect(url_for("event.listar_eventos"))
    

# -----------------------------
# 🌐 Página pública por token
# -----------------------------
@event_bp.route("/publico/<string:public_token>", methods=["GET"])
def evento_publico_token(public_token):
    evento = Evento.query.filter_by(public_token=public_token).first_or_404()

    if evento.token_expira_em and evento.token_expira_em < datetime.utcnow():
        return render_template("eventos/evento_expirado.html", evento=evento), 410

    return render_template("eventos/evento_publico.html", evento=evento)


# -----------------------------
# 📅 Feed de Eventos para FullCalendar (JSON)
# -----------------------------
@event_bp.route("/api/calendario", methods=["GET"])
@login_required
@permission_required("eventos", "view")
def api_calendario():
    start_str = request.args.get("start")
    end_str = request.args.get("end")
    termo = request.args.get("q", "").strip().lower()

    query = Evento.query

    # Filtro de intervalo de datas enviado pelo FullCalendar
    if start_str:
        try:
            start_clean = start_str[:19]
            start_dt = datetime.fromisoformat(start_clean)
            query = query.filter(Evento.data_fim >= start_dt)
        except Exception:
            pass

    if end_str:
        try:
            end_clean = end_str[:19]
            end_dt = datetime.fromisoformat(end_clean)
            query = query.filter(Evento.data_inicio <= end_dt)
        except Exception:
            pass

    # Filtro de busca textual (se fornecido)
    if termo:
        query = query.filter(
            (Evento.titulo.ilike(f"%{termo}%")) |
            (Evento.tipo.ilike(f"%{termo}%")) |
            (Evento.organizador.ilike(f"%{termo}%"))
        )

    eventos = query.all()

    can_edit = has_permission("eventos", "edit")
    can_delete = has_permission("eventos", "delete")
    can_view = has_permission("eventos", "view")

    STATUS_CONFIG = {
        "confirmado": {"bg": "#2563eb", "border": "#1d4ed8", "badge": "bg-success", "text": "Confirmado"},
        "planejado": {"bg": "#f59e0b", "border": "#d97706", "badge": "bg-warning", "text": "Planejado"},
        "em andamento": {"bg": "#0ea5e9", "border": "#0284c7", "badge": "bg-info", "text": "Em Andamento"},
        "em_andamento": {"bg": "#0ea5e9", "border": "#0284c7", "badge": "bg-info", "text": "Em Andamento"},
        "concluído": {"bg": "#64748b", "border": "#475569", "badge": "bg-secondary", "text": "Concluído"},
        "concluido": {"bg": "#64748b", "border": "#475569", "badge": "bg-secondary", "text": "Concluído"},
        "cancelado": {"bg": "#ef4444", "border": "#dc2626", "badge": "bg-danger", "text": "Cancelado"},
    }

    TIPO_MAP = {
        "culto especial": "Culto Especial",
        "culto_especial": "Culto Especial",
        "retiro": "Retiro",
        "batismo": "Batismo",
        "reunião": "Reunião",
        "reuniao": "Reunião",
        "evangelismo": "Evangelismo",
        "conferência": "Conferência",
        "conferencia": "Conferência",
        "outros": "Outros"
    }

    eventos_json = []
    for ev in eventos:
        status_key = (ev.status or "confirmado").lower().strip()
        status_cfg = STATUS_CONFIG.get(status_key, {
            "bg": "#2563eb", "border": "#1d4ed8", "badge": "bg-primary", "text": status_key.capitalize()
        })
        tipo_formatado = TIPO_MAP.get((ev.tipo or "").lower().strip(), (ev.tipo or "Geral").title())

        # Formato ISO seguro para compatibilidade
        start_iso = ev.data_inicio.strftime("%Y-%m-%dT%H:%M:%S") if ev.data_inicio else None
        end_iso = ev.data_fim.strftime("%Y-%m-%dT%H:%M:%S") if ev.data_fim else None

        eventos_json.append({
            "id": ev.id,
            "title": ev.titulo,
            "start": start_iso,
            "end": end_iso,
            "backgroundColor": status_cfg["bg"],
            "borderColor": status_cfg["border"],
            "textColor": "#ffffff",
            "extendedProps": {
                "id": ev.id,
                "titulo": ev.titulo,
                "descricao": ev.descricao or "",
                "tipo": ev.tipo or "",
                "tipo_formatado": tipo_formatado,
                "status": ev.status or "confirmado",
                "status_formatado": status_cfg["text"],
                "status_badge": status_cfg["badge"],
                "local": ev.local or "-",
                "organizador": ev.organizador or "-",
                "data_inicio_fmt": ev.data_inicio.strftime("%d/%m/%Y %H:%M") if ev.data_inicio else "-",
                "data_fim_fmt": ev.data_fim.strftime("%d/%m/%Y %H:%M") if ev.data_fim else "-",
                "public_url": url_for("event.evento_publico_token", public_token=ev.public_token),
                "edit_url": url_for("event.editar_evento", id=ev.id),
                "delete_url": url_for("event.excluir_evento", id=ev.id),
                "can_edit": can_edit,
                "can_delete": can_delete,
                "can_view": can_view
            }
        })

    return jsonify(eventos_json)
