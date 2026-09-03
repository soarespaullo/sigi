import secrets
from datetime import datetime, date, timedelta, timezone
from collections import defaultdict
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, abort
from flask_login import login_required, current_user
from sqlalchemy import or_, extract

from app.extensions import db
from app.models import (
    Escala, EscalaItem, Equipe, EquipeFuncao, EquipeMembro,
    Member, Evento, User
)
from app.routes.escala.forms import (
    EscalaForm, EquipeForm, EquipeFuncaoForm, EquipeMembroForm,
    AdicionarVoluntarioForm, SubstituirVoluntarioForm, DuplicarEscalaForm
)
from app.services.escala_service import EscalaService
from app.decorators import permission_required
from utils.logs import registrar_log
from utils.sanitizer import sanitizar_html

escala_bp = Blueprint("escala", __name__, url_prefix="/escalas")


# ---------------------------------------------------------------------------
# 📋 Listagem de Escalas (Visão Lista & Grade/Calendário)
# ---------------------------------------------------------------------------
@escala_bp.route("/", methods=["GET"])
@login_required
@permission_required("escalas", "view")
def listar_escalas():
    termo = request.args.get("q", "").strip()
    status_filtro = request.args.get("status", "")
    equipe_filtro = request.args.get("equipe_id", type=int)
    modo_visualizacao = request.args.get("modo", "lista")  # "lista" ou "calendario"
    page = request.args.get("page", 1, type=int)

    query = Escala.query

    if status_filtro:
        query = query.filter(Escala.status == status_filtro)

    if termo:
        query = query.filter(
            or_(
                Escala.titulo.ilike(f"%{termo}%"),
                Escala.local.ilike(f"%{termo}%"),
                Escala.observacoes.ilike(f"%{termo}%")
            )
        )

    if equipe_filtro:
        query = query.join(EscalaItem).filter(EscalaItem.equipe_id == equipe_filtro).distinct()

    # Ordenação: próximas escalas primeiro (ASC a partir de hoje) e depois passadas (DESC)
    hoje = date.today()
    from sqlalchemy import case
    order_grupo = case((Escala.data >= hoje, 0), else_=1).asc()
    order_data = case((Escala.data >= hoje, Escala.data), else_=None).asc()
    order_passadas = case((Escala.data < hoje, Escala.data), else_=None).desc()

    query = query.order_by(order_grupo, order_data, order_passadas, Escala.hora_inicio.asc())

    # Paginação na visão de lista (na visão calendário traz as mais recentes/próximas)
    if modo_visualizacao == "calendario":
        escalas = query.limit(50).all()
        escalas_paginadas = None
    else:
        escalas_paginadas = query.paginate(page=page, per_page=12)
        escalas = escalas_paginadas.items

    # Estatísticas do mês atual para cards superiores
    mes_atual = hoje.month
    ano_atual = hoje.year
    total_mes = Escala.query.filter(
        extract("month", Escala.data) == mes_atual,
        extract("year", Escala.data) == ano_atual
    ).count()

    total_confirmadas = Escala.query.filter(
        extract("month", Escala.data) == mes_atual,
        extract("year", Escala.data) == ano_atual,
        Escala.status == "confirmada"
    ).count()

    total_pendentes = Escala.query.filter(
        extract("month", Escala.data) == mes_atual,
        extract("year", Escala.data) == ano_atual,
        Escala.status.in_(["rascunho", "publicada"])
    ).count()

    equipes = Equipe.query.filter_by(ativo=True).order_by(Equipe.nome.asc()).all()

    return render_template(
        "escalas/listar_escalas.html",
        escalas=escalas,
        escalas_paginadas=escalas_paginadas,
        equipes=equipes,
        termo=termo,
        status_filtro=status_filtro,
        equipe_filtro=equipe_filtro,
        modo_visualizacao=modo_visualizacao,
        total_mes=total_mes,
        total_confirmadas=total_confirmadas,
        total_pendentes=total_pendentes,
        hoje=hoje
    )


# ---------------------------------------------------------------------------
# ➕ Criar Nova Escala
# ---------------------------------------------------------------------------
@escala_bp.route("/nova", methods=["GET", "POST"])
@login_required
@permission_required("escalas", "create")
def nova_escala():
    form = EscalaForm()

    # Preenche opções de eventos futuros do calendário oficial
    hoje = datetime.now()
    eventos_proximos = (
        Evento.query
        .filter(Evento.data_fim >= hoje)
        .order_by(Evento.data_inicio.asc())
        .limit(30)
        .all()
    )
    form.evento_id.choices = [(0, "-- Nenhum (Escala Independente) --")] + [
        (e.id, f"{e.titulo} ({e.data_inicio.strftime('%d/%m/%Y %H:%M')})")
        for e in eventos_proximos
    ]

    # Sugere data se passada via query param
    data_param = request.args.get("data")
    if data_param and not form.data.data:
        try:
            form.data.data = datetime.strptime(data_param, "%Y-%m-%d").date()
        except ValueError:
            pass

    evento_id_param = request.args.get("evento_id", type=int)
    if evento_id_param and request.method == "GET":
        ev = db.session.get(Evento, evento_id_param)
        if ev:
            form.evento_id.data = ev.id
            form.titulo.data = f"Escala — {ev.titulo}"
            form.data.data = ev.data_inicio.date()
            form.hora_inicio.data = ev.data_inicio.strftime("%H:%M")
            form.hora_fim.data = ev.data_fim.strftime("%H:%M")
            form.local.data = ev.local or "Templo Principal"

    if form.validate_on_submit():
        evento_id = form.evento_id.data if form.evento_id.data and form.evento_id.data > 0 else None

        nova = Escala(
            titulo=form.titulo.data.strip(),
            data=form.data.data,
            hora_inicio=form.hora_inicio.data.strip(),
            hora_fim=form.hora_fim.data.strip() if form.hora_fim.data else None,
            evento_id=evento_id,
            local=form.local.data.strip() if form.local.data else "Templo Principal",
            observacoes=sanitizar_html(form.observacoes.data) if form.observacoes.data else None,
            status=form.status.data,
            criado_por_id=current_user.id
        )

        db.session.add(nova)
        db.session.commit()

        registrar_log(current_user.nome, f"Criou a escala: {nova.titulo} para {nova.data.strftime('%d/%m/%Y')}", "sucesso")
        flash(f"Escala '{nova.titulo}' criada com sucesso! Agora adicione as equipes e pessoas escaladas.", "success")
        return redirect(url_for("escala.ver_escala", id=nova.id))

    return render_template("escalas/escala_form.html", form=form, modo="nova")


# ---------------------------------------------------------------------------
# 👁️ Visualizar & Gerenciar Escala Detalhada
# ---------------------------------------------------------------------------
@escala_bp.route("/<int:id>", methods=["GET"])
@login_required
@permission_required("escalas", "view")
def ver_escala(id):
    escala = Escala.query.get_or_404(id)

    # Agrupa itens por equipe para visualização organizada
    itens_por_equipe = defaultdict(list)
    for item in escala.itens:
        itens_por_equipe[item.equipe].append(item)

    # Formulários auxiliares para ações modais
    form_voluntario = AdicionarVoluntarioForm()
    equipes_ativas = Equipe.query.filter_by(ativo=True).order_by(Equipe.nome.asc()).all()
    form_voluntario.equipe_id.choices = [(eq.id, eq.nome) for eq in equipes_ativas]
    form_voluntario.funcao_id.choices = [(0, "-- Nenhuma / Função Geral --")]

    # Membros ativos para seleção rápida
    membros_ativos = (
        Member.query
        .filter(
            (Member.status.is_(None)) | (Member.status == "Ativo"),
            Member.data_saida.is_(None)
        )
        .order_by(Member.nome.asc())
        .all()
    )
    form_voluntario.membro_id.choices = [(m.id, f"{m.nome} ({m.funcao or 'Membro'})") for m in membros_ativos]

    form_substituir = SubstituirVoluntarioForm()
    form_substituir.novo_membro_id.choices = [(m.id, f"{m.nome} ({m.funcao or 'Membro'})") for m in membros_ativos]

    form_duplicar = DuplicarEscalaForm()
    form_duplicar.nova_data.data = escala.data + timedelta(days=7)  # Sugere mesmo dia da semana seguinte
    form_duplicar.nova_hora_inicio.data = escala.hora_inicio
    form_duplicar.nova_hora_fim.data = escala.hora_fim
    form_duplicar.novo_titulo.data = escala.titulo

    # URL pública com token para compartilhamento
    link_publico = url_for("escala.escala_publica", token=escala.public_token, _external=True)

    # Texto formatado pronto para compartilhar no WhatsApp
    data_formatada = escala.data.strftime("%d/%m/%Y")
    dia_semana = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"][escala.data.weekday()]
    
    msg_zap_lines = [
        f"📅 *ESCALA — {escala.titulo.upper()}*",
        f"🗓️ Data: {dia_semana}, {data_formatada} às {escala.hora_inicio}",
        f"📍 Local: {escala.local or 'Templo Principal'}",
        ""
    ]
    for eq, itens in itens_por_equipe.items():
        msg_zap_lines.append(f"*{eq.nome.upper()}*")
        for item in itens:
            funcao_str = f" ({item.funcao.nome})" if item.funcao else ""
            status_icone = "✅" if item.status == "confirmado" else ("⏳" if item.status == "pendente" else "🔄")
            msg_zap_lines.append(f"• {item.membro.nome}{funcao_str} - {status_icone} {item.status_display}")
        msg_zap_lines.append("")

    msg_zap_lines.append(f"🔗 *Consulte os detalhes e confirme sua presença:* {link_publico}")
    texto_whatsapp = "\n".join(msg_zap_lines)

    return render_template(
        "escalas/escala_detalhe.html",
        escala=escala,
        itens_por_equipe=itens_por_equipe,
        equipes_ativas=equipes_ativas,
        form_voluntario=form_voluntario,
        form_substituir=form_substituir,
        form_duplicar=form_duplicar,
        link_publico=link_publico,
        texto_whatsapp=texto_whatsapp
    )


# ---------------------------------------------------------------------------
# ✏️ Editar Escala
# ---------------------------------------------------------------------------
@escala_bp.route("/editar/<int:id>", methods=["GET", "POST"])
@login_required
@permission_required("escalas", "edit")
def editar_escala(id):
    escala = Escala.query.get_or_404(id)
    form = EscalaForm(obj=escala)

    # Eventos para opção de vínculo
    eventos_proximos = (
        Evento.query
        .order_by(Evento.data_inicio.desc())
        .limit(40)
        .all()
    )
    form.evento_id.choices = [(0, "-- Nenhum (Escala Independente) --")] + [
        (e.id, f"{e.titulo} ({e.data_inicio.strftime('%d/%m/%Y %H:%M')})")
        for e in eventos_proximos
    ]

    if form.validate_on_submit():
        evento_id = form.evento_id.data if form.evento_id.data and form.evento_id.data > 0 else None

        escala.titulo = form.titulo.data.strip()
        escala.data = form.data.data
        escala.hora_inicio = form.hora_inicio.data.strip()
        escala.hora_fim = form.hora_fim.data.strip() if form.hora_fim.data else None
        escala.evento_id = evento_id
        escala.local = form.local.data.strip() if form.local.data else "Templo Principal"
        escala.observacoes = sanitizar_html(form.observacoes.data) if form.observacoes.data else None
        escala.status = form.status.data

        db.session.commit()
        registrar_log(current_user.nome, f"Editou a escala: {escala.titulo}", "sucesso")
        flash(f"Escala '{escala.titulo}' atualizada com sucesso!", "success")
        return redirect(url_for("escala.ver_escala", id=escala.id))

    return render_template("escalas/escala_form.html", form=form, escala=escala, modo="editar")


# ---------------------------------------------------------------------------
# ❌ Excluir Escala
# ---------------------------------------------------------------------------
@escala_bp.route("/excluir/<int:id>", methods=["POST"])
@login_required
@permission_required("escalas", "delete")
def excluir_escala(id):
    escala = Escala.query.get_or_404(id)
    titulo = escala.titulo
    db.session.delete(escala)
    db.session.commit()

    registrar_log(current_user.nome, f"Excluiu a escala: {titulo}", "sucesso")
    flash(f"Escala '{titulo}' excluída com sucesso!", "success")
    return redirect(url_for("escala.listar_escalas"))


# ---------------------------------------------------------------------------
# 🔄 Alterar Status Geral da Escala (Publicar, Confirmar, Concluir, Cancelar)
# ---------------------------------------------------------------------------
@escala_bp.route("/<int:id>/status", methods=["POST"])
@login_required
@permission_required("escalas", "edit")
def alterar_status_escala(id):
    escala = Escala.query.get_or_404(id)
    novo_status = request.form.get("status", "").strip()

    status_validos = ["rascunho", "publicada", "confirmada", "concluida", "cancelada"]
    if novo_status in status_validos:
        escala.status = novo_status
        db.session.commit()
        registrar_log(current_user.nome, f"Alterou status da escala '{escala.titulo}' para '{novo_status}'", "sucesso")
        flash(f"Status da escala alterado para '{escala.status_display}'!", "success")
    else:
        flash("Status inválido.", "danger")

    return redirect(url_for("escala.ver_escala", id=escala.id))


# ---------------------------------------------------------------------------
# 👥 Adicionar Voluntário à Escala
# ---------------------------------------------------------------------------
@escala_bp.route("/<int:id>/adicionar-item", methods=["POST"])
@login_required
@permission_required("escalas", "edit")
def adicionar_item(id):
    escala = Escala.query.get_or_404(id)

    equipe_id = request.form.get("equipe_id", type=int)
    membro_id = request.form.get("membro_id", type=int)
    funcao_id = request.form.get("funcao_id", type=int)
    observacao = request.form.get("observacao", "").strip()

    if not equipe_id or not membro_id:
        flash("Selecione a equipe e o voluntário.", "warning")
        return redirect(url_for("escala.ver_escala", id=escala.id))

    if funcao_id == 0:
        funcao_id = None

    # Validação inteligente de conflitos
    analise = EscalaService.verificar_conflitos(
        membro_id=membro_id,
        escala_data=escala.data,
        hora_inicio=escala.hora_inicio,
        hora_fim=escala.hora_fim,
        escala_id=escala.id
    )

    if analise["possui_conflito"]:
        msg = f"Conflito para {analise['membro_nome']}: " + " | ".join(analise["conflitos"])
        flash(msg, "danger")
        return redirect(url_for("escala.ver_escala", id=escala.id))

    # Criação do item
    item = EscalaItem(
        escala_id=escala.id,
        equipe_id=equipe_id,
        funcao_id=funcao_id,
        membro_id=membro_id,
        observacao=observacao if observacao else None,
        status="pendente"
    )

    db.session.add(item)
    db.session.commit()

    membro = db.session.get(Member, membro_id)
    nome_membro = membro.nome if membro else f"Membro #{membro_id}"
    registrar_log(current_user.nome, f"Escalou {nome_membro} na escala '{escala.titulo}'", "sucesso")

    if analise["avisos"]:
        flash(f"{nome_membro} escalado com sucesso! Observação: {analise['avisos'][0]}", "warning")
    else:
        flash(f"{nome_membro} escalado com sucesso!", "success")

    return redirect(url_for("escala.ver_escala", id=escala.id))


# ---------------------------------------------------------------------------
# ❌ Remover Voluntário da Escala
# ---------------------------------------------------------------------------
@escala_bp.route("/item/<int:item_id>/remover", methods=["POST"])
@login_required
@permission_required("escalas", "edit")
def remover_item(item_id):
    item = EscalaItem.query.get_or_404(item_id)
    escala_id = item.escala_id
    nome_membro = item.membro.nome if item.membro else "Voluntário"

    db.session.delete(item)
    db.session.commit()

    registrar_log(current_user.nome, f"Removeu {nome_membro} da escala #{escala_id}", "sucesso")
    flash(f"{nome_membro} removido da escala.", "info")
    return redirect(url_for("escala.ver_escala", id=escala_id))


# ---------------------------------------------------------------------------
# 🔄 Substituir Voluntário Mantendo Histórico
# ---------------------------------------------------------------------------
@escala_bp.route("/item/<int:item_id>/substituir", methods=["POST"])
@login_required
@permission_required("escalas", "gerenciar")
def substituir_item(item_id):
    item = EscalaItem.query.get_or_404(item_id)
    novo_membro_id = request.form.get("novo_membro_id", type=int)
    motivo = request.form.get("motivo", "").strip()

    if not novo_membro_id or novo_membro_id == item.membro_id:
        flash("Selecione um voluntário substituto diferente do atual.", "warning")
        return redirect(url_for("escala.ver_escala", id=item.escala_id))

    # Analisa se o substituto tem conflito de horário
    analise = EscalaService.verificar_conflitos(
        membro_id=novo_membro_id,
        escala_data=item.escala.data,
        hora_inicio=item.escala.hora_inicio,
        hora_fim=item.escala.hora_fim,
        escala_id=item.escala_id
    )

    if analise["possui_conflito"]:
        flash(f"Não foi possível substituir: {analise['conflitos'][0]}", "danger")
        return redirect(url_for("escala.ver_escala", id=item.escala_id))

    EscalaService.substituir_voluntario(
        item_id=item.id,
        novo_membro_id=novo_membro_id,
        motivo=motivo,
        usuario=current_user
    )

    flash("Substituição realizada com sucesso! O histórico do voluntário original foi preservado.", "success")
    return redirect(url_for("escala.ver_escala", id=item.escala_id))


# ---------------------------------------------------------------------------
# 📌 Alterar Status de Presença do Item (Confirmar / Recusar / Pendente)
# ---------------------------------------------------------------------------
@escala_bp.route("/item/<int:item_id>/status", methods=["POST"])
@login_required
@permission_required("escalas", "edit")
def alterar_status_item(item_id):
    item = EscalaItem.query.get_or_404(item_id)
    novo_status = request.form.get("status", "").strip()

    if novo_status in ["confirmado", "pendente", "recusado"]:
        item.status = novo_status
        if novo_status == "confirmado":
            item.confirmado_em = datetime.now(timezone.utc)
        db.session.commit()
        flash(f"Presença de {item.membro.nome} alterada para '{item.status_display}'!", "success")
    else:
        flash("Status de voluntário inválido.", "danger")

    return redirect(url_for("escala.ver_escala", id=item.escala_id))


# ---------------------------------------------------------------------------
# 📑 Duplicar Escala Anterior (Clonagem Segura com 1 Clique)
# ---------------------------------------------------------------------------
@escala_bp.route("/<int:id>/duplicar", methods=["POST"])
@login_required
@permission_required("escalas", "create")
def duplicar_escala(id):
    form = DuplicarEscalaForm()
    if form.validate_on_submit():
        nova_escala = EscalaService.duplicar_escala(
            escala_id=id,
            nova_data=form.nova_data.data,
            nova_hora_inicio=form.nova_hora_inicio.data,
            nova_hora_fim=form.nova_hora_fim.data,
            novo_titulo=form.novo_titulo.data,
            usuario=current_user
        )
        flash(f"Escala duplicada com sucesso para {nova_escala.data.strftime('%d/%m/%Y')}! Revise as equipes e voluntários.", "success")
        return redirect(url_for("escala.ver_escala", id=nova_escala.id))

    flash("Dados inválidos para duplicação.", "danger")
    return redirect(url_for("escala.ver_escala", id=id))


# ---------------------------------------------------------------------------
# 🖨️ Impressão & Mural A4 da Escala
# ---------------------------------------------------------------------------
@escala_bp.route("/<int:id>/imprimir", methods=["GET"])
@login_required
@permission_required("escalas", "view")
def imprimir_escala(id):
    escala = Escala.query.get_or_404(id)
    itens_por_equipe = defaultdict(list)
    for item in escala.itens:
        itens_por_equipe[item.equipe].append(item)

    return render_template(
        "escalas/escala_imprimir.html",
        escala=escala,
        itens_por_equipe=itens_por_equipe
    )


# ---------------------------------------------------------------------------
# 🌐 Página Pública para Voluntários (Visualização e Confirmação no Celular)
# ---------------------------------------------------------------------------
@escala_bp.route("/publico/<string:token>", methods=["GET"])
def escala_publica(token):
    escala = Escala.query.filter_by(public_token=token).first_or_404()

    itens_por_equipe = defaultdict(list)
    for item in escala.itens:
        itens_por_equipe[item.equipe].append(item)

    return render_template(
        "escalas/escala_publica.html",
        escala=escala,
        itens_por_equipe=itens_por_equipe
    )


@escala_bp.route("/publico/<string:token>/item/<int:item_id>/confirmar", methods=["POST"])
def publico_confirmar_item(token, item_id):
    escala = Escala.query.filter_by(public_token=token).first_or_404()
    item = EscalaItem.query.filter_by(id=item_id, escala_id=escala.id).first_or_404()

    item.status = "confirmado"
    item.confirmado_em = datetime.now(timezone.utc)
    db.session.commit()

    flash(f"Obrigado, {item.membro.nome}! Sua presença foi confirmada com sucesso.", "success")
    return redirect(url_for("escala.escala_publica", token=token))


@escala_bp.route("/publico/<string:token>/item/<int:item_id>/recusar", methods=["POST"])
def publico_recusar_item(token, item_id):
    escala = Escala.query.filter_by(public_token=token).first_or_404()
    item = EscalaItem.query.filter_by(id=item_id, escala_id=escala.id).first_or_404()

    motivo = request.form.get("motivo", "").strip()
    item.status = "recusado"
    if motivo:
        item.observacao = f"Ausência informada: {motivo}"
    db.session.commit()

    flash(f"Ausência registrada para {item.membro.nome}. A liderança foi notificada.", "warning")
    return redirect(url_for("escala.escala_publica", token=token))


# ===========================================================================
# 🏛️ GESTÃO DE EQUIPES / DEPARTAMENTOS & FUNÇÕES
# ===========================================================================

@escala_bp.route("/equipes/", methods=["GET", "POST"])
@login_required
@permission_required("escalas", "gerenciar")
def listar_equipes():
    form = EquipeForm()

    # Opções de membros para líder da equipe
    membros = (
        Member.query
        .filter(
            (Member.status.is_(None)) | (Member.status == "Ativo"),
            Member.data_saida.is_(None)
        )
        .order_by(Member.nome.asc())
        .all()
    )
    form.lider_id.choices = [(0, "-- Selecione um Líder --")] + [(m.id, m.nome) for m in membros]

    if form.validate_on_submit():
        lider_id = form.lider_id.data if form.lider_id.data and form.lider_id.data > 0 else None

        nova_equipe = Equipe(
            nome=form.nome.data.strip(),
            descricao=sanitizar_html(form.descricao.data) if form.descricao.data else None,
            cor=form.cor.data.strip() if form.cor.data else "#0d6efd",
            icone=form.icone.data.strip() if form.icone.data else "bi-people",
            lider_id=lider_id,
            ativo=form.ativo.data
        )
        db.session.add(nova_equipe)
        db.session.commit()

        registrar_log(current_user.nome, f"Criou a equipe: {nova_equipe.nome}", "sucesso")
        flash(f"Equipe '{nova_equipe.nome}' cadastrada com sucesso!", "success")
        return redirect(url_for("escala.detalhes_equipe", id=nova_equipe.id))

    equipes = Equipe.query.order_by(Equipe.ativo.desc(), Equipe.nome.asc()).all()
    return render_template("escalas/equipes_listar.html", equipes=equipes, form=form)


@escala_bp.route("/equipes/<int:id>", methods=["GET", "POST"])
@login_required
@permission_required("escalas", "gerenciar")
def detalhes_equipe(id):
    equipe = Equipe.query.get_or_404(id)
    form_editar = EquipeForm(obj=equipe)

    membros_ativos = (
        Member.query
        .filter(
            (Member.status.is_(None)) | (Member.status == "Ativo"),
            Member.data_saida.is_(None)
        )
        .order_by(Member.nome.asc())
        .all()
    )
    form_editar.lider_id.choices = [(0, "-- Selecione um Líder --")] + [(m.id, m.nome) for m in membros_ativos]

    if request.method == "POST" and "editar_equipe" in request.form:
        if form_editar.validate_on_submit():
            equipe.nome = form_editar.nome.data.strip()
            equipe.descricao = sanitizar_html(form_editar.descricao.data) if form_editar.descricao.data else None
            equipe.cor = form_editar.cor.data.strip() if form_editar.cor.data else "#0d6efd"
            equipe.icone = form_editar.icone.data.strip() if form_editar.icone.data else "bi-people"
            equipe.lider_id = form_editar.lider_id.data if form_editar.lider_id.data and form_editar.lider_id.data > 0 else None
            equipe.ativo = form_editar.ativo.data

            db.session.commit()
            registrar_log(current_user.nome, f"Atualizou equipe: {equipe.nome}", "sucesso")
            flash(f"Equipe '{equipe.nome}' atualizada com sucesso!", "success")
            return redirect(url_for("escala.detalhes_equipe", id=equipe.id))

    form_funcao = EquipeFuncaoForm()
    form_membro = EquipeMembroForm()

    # Membros que ainda não fazem parte desta equipe
    membros_ja_na_equipe = {em.membro_id for em in equipe.membros}
    membros_disponiveis = [m for m in membros_ativos if m.id not in membros_ja_na_equipe]
    form_membro.membro_id.choices = [(m.id, m.nome) for m in membros_disponiveis]

    # Garante que qualquer função criada para a equipe esteja ativa
    precisa_commit = False
    for f in equipe.funcoes:
        if not f.ativo:
            f.ativo = True
            precisa_commit = True
    if precisa_commit:
        db.session.commit()

    form_membro.funcao_padrao_id.choices = [(0, "-- Nenhuma / Função Geral --")] + [
        (f.id, f.nome) for f in equipe.funcoes
    ]

    return render_template(
        "escalas/equipe_detalhe.html",
        equipe=equipe,
        form_editar=form_editar,
        form_funcao=form_funcao,
        form_membro=form_membro,
        membros_disponiveis=membros_disponiveis
    )


@escala_bp.route("/equipes/<int:id>/adicionar-funcao", methods=["POST"])
@login_required
@permission_required("escalas", "gerenciar")
def equipe_adicionar_funcao(id):
    equipe = Equipe.query.get_or_404(id)
    form = EquipeFuncaoForm()

    if form.validate_on_submit():
        funcao = EquipeFuncao(
            equipe_id=equipe.id,
            nome=form.nome.data.strip(),
            descricao=form.descricao.data.strip() if form.descricao.data else None,
            ordem=form.ordem.data or 0,
            ativo=True
        )
        db.session.add(funcao)
        db.session.commit()
        flash(f"Função '{funcao.nome}' adicionada à equipe {equipe.nome}!", "success")
    else:
        flash("Nome da função é obrigatório.", "warning")

    return redirect(url_for("escala.detalhes_equipe", id=equipe.id))


@escala_bp.route("/equipes/<int:id>/excluir-funcao/<int:funcao_id>", methods=["POST"])
@login_required
@permission_required("escalas", "gerenciar")
def equipe_excluir_funcao(id, funcao_id):
    equipe = Equipe.query.get_or_404(id)
    funcao = EquipeFuncao.query.filter_by(id=funcao_id, equipe_id=equipe.id).first_or_404()
    nome_funcao = funcao.nome

    db.session.delete(funcao)
    db.session.commit()
    flash(f"Função '{nome_funcao}' removida.", "info")
    return redirect(url_for("escala.detalhes_equipe", id=equipe.id))


@escala_bp.route("/equipes/<int:id>/adicionar-membro", methods=["POST"])
@login_required
@permission_required("escalas", "gerenciar")
def equipe_adicionar_membro(id):
    equipe = Equipe.query.get_or_404(id)
    membro_id = request.form.get("membro_id", type=int)
    funcao_padrao_id = request.form.get("funcao_padrao_id", type=int)

    if not membro_id:
        flash("Selecione um membro para adicionar à equipe.", "warning")
        return redirect(url_for("escala.detalhes_equipe", id=equipe.id))

    if funcao_padrao_id == 0:
        funcao_padrao_id = None

    existe = EquipeMembro.query.filter_by(equipe_id=equipe.id, membro_id=membro_id).first()
    if existe:
        flash("Este membro já faz parte desta equipe.", "info")
    else:
        vinculo = EquipeMembro(
            equipe_id=equipe.id,
            membro_id=membro_id,
            funcao_padrao_id=funcao_padrao_id,
            ativo=True
        )
        db.session.add(vinculo)
        db.session.commit()
        membro = db.session.get(Member, membro_id)
        flash(f"{membro.nome} adicionado(a) à equipe {equipe.nome}!", "success")

    return redirect(url_for("escala.detalhes_equipe", id=equipe.id))


@escala_bp.route("/equipes/<int:id>/editar-membro/<int:membro_id>", methods=["POST"])
@login_required
@permission_required("escalas", "gerenciar")
def equipe_editar_membro(id, membro_id):
    equipe = Equipe.query.get_or_404(id)
    vinculo = EquipeMembro.query.filter_by(equipe_id=equipe.id, membro_id=membro_id).first_or_404()
    nova_funcao_id = request.form.get("funcao_padrao_id", type=int)

    if nova_funcao_id == 0 or not nova_funcao_id:
        vinculo.funcao_padrao_id = None
    else:
        funcao = EquipeFuncao.query.filter_by(id=nova_funcao_id, equipe_id=equipe.id).first()
        if funcao:
            vinculo.funcao_padrao_id = funcao.id

    db.session.commit()
    nome_membro = vinculo.membro.nome if vinculo.membro else "Voluntário"
    flash(f"Função de {nome_membro} atualizada com sucesso!", "success")
    return redirect(url_for("escala.detalhes_equipe", id=equipe.id))


@escala_bp.route("/equipes/<int:id>/remover-membro/<int:membro_id>", methods=["POST"])
@login_required
@permission_required("escalas", "gerenciar")
def equipe_remover_membro(id, membro_id):
    equipe = Equipe.query.get_or_404(id)
    vinculo = EquipeMembro.query.filter_by(equipe_id=equipe.id, membro_id=membro_id).first_or_404()
    nome_membro = vinculo.membro.nome if vinculo.membro else f"Membro #{membro_id}"

    db.session.delete(vinculo)
    db.session.commit()
    flash(f"{nome_membro} removido(a) da equipe {equipe.nome}.", "info")
    return redirect(url_for("escala.detalhes_equipe", id=equipe.id))


# ---------------------------------------------------------------------------
# 🔍 API para Carregar Funções e Voluntários de uma Equipe (para modais dinâmicos)
# ---------------------------------------------------------------------------
@escala_bp.route("/api/equipe/<int:equipe_id>/dados", methods=["GET"])
@login_required
def api_equipe_dados(equipe_id):
    equipe = Equipe.query.get_or_404(equipe_id)

    funcoes = [{"id": f.id, "nome": f.nome} for f in equipe.funcoes if f.ativo]
    membros = [
        {
            "id": em.membro.id,
            "nome": em.membro.nome,
            "funcao_padrao_id": em.funcao_padrao_id,
            "funcao_padrao_nome": em.funcao_padrao.nome if em.funcao_padrao else ""
        }
        for em in equipe.membros if em.ativo
    ]

    return jsonify({
        "equipe_id": equipe.id,
        "nome": equipe.nome,
        "cor": equipe.cor,
        "funcoes": funcoes,
        "membros": membros
    })


# ---------------------------------------------------------------------------
# ⚡ API para Verificação de Conflitos em Tempo Real
# ---------------------------------------------------------------------------
@escala_bp.route("/api/verificar-conflito", methods=["POST"])
@login_required
def api_verificar_conflito():
    dados = request.get_json() or {}
    membro_id = dados.get("membro_id")
    data_str = dados.get("data")
    hora_inicio = dados.get("hora_inicio", "18:00")
    hora_fim = dados.get("hora_fim")
    escala_id = dados.get("escala_id")

    if not membro_id or not data_str:
        return jsonify({"possui_conflito": False, "conflitos": [], "avisos": []})

    try:
        escala_data = datetime.strptime(data_str, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"possui_conflito": False, "conflitos": [], "avisos": []})

    resultado = EscalaService.verificar_conflitos(
        membro_id=int(membro_id),
        escala_data=escala_data,
        hora_inicio=hora_inicio,
        hora_fim=hora_fim,
        escala_id=int(escala_id) if escala_id else None
    )

    return jsonify(resultado)
