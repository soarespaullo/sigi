from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
from app.extensions import db
from app.models import Member, User, Log
from app.models.ebd import EbdConfig, EbdPeriodo, EbdClasse, EbdProfessor, EbdMatricula, EbdAula, EbdFrequencia
from app.decorators import permission_required
from utils.sanitizer import sanitizar_html
from .forms import (
    EbdConfigForm, EbdPeriodoForm, EbdClasseForm,
    EbdProfessorForm, EbdMatriculaForm, EbdTransferenciaForm, EbdAulaForm
)

ebd_bp = Blueprint("ebd", __name__, url_prefix="/ebd")

def registrar_log_ebd(tarefa, resultado="sucesso"):
    try:
        user_id_str = getattr(current_user, "nome", None) or getattr(current_user, "email", "desconhecido")
        log = Log(
            usuario=user_id_str,
            tarefa=tarefa,
            resultado=resultado,
            datahora=datetime.now(),
            ip=request.remote_addr or "desconhecido"
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao registrar log EBD: {e}")


def obter_ou_criar_config():
    config = EbdConfig.query.first()
    if not config:
        config = EbdConfig(
            nome="Escola Bíblica Dominical",
            descricao="Ministério de Ensino e Discipulado da Igreja",
            dia_semana="Domingo",
            horario_inicio="09:00",
            horario_termino="10:30"
        )
        db.session.add(config)
        db.session.commit()
    return config


def usuario_pode_gerenciar_classe(classe_id):
    """
    Verifica se o usuário logado possui permissão administrativa total (admin / ebd:edit)
    ou se é professor ativo vinculado a esta classe específica da EBD.
    """
    if current_user.is_admin or current_user.has_permission("ebd", "edit"):
        return True
    if not current_user.member_id:
        return False
    prof = EbdProfessor.query.filter_by(
        classe_id=classe_id,
        membro_id=current_user.member_id,
        status="ativo"
    ).first()
    return prof is not None


# ==============================================================================
# 0. 👨‍🏫 PORTAL DO PROFESSOR — MINHAS CLASSES
# ==============================================================================
@ebd_bp.route("/minhas-classes")
@login_required
@permission_required("ebd", "view")
def minhas_classes():
    membro_id = current_user.member_id
    is_coordenador = current_user.is_admin or current_user.has_permission("ebd", "edit")

    if is_coordenador:
        classes = EbdClasse.query.filter_by(status="ativa").order_by(EbdClasse.nome).all()
    elif membro_id:
        profs = EbdProfessor.query.filter_by(membro_id=membro_id, status="ativo").all()
        classes_ids = [p.classe_id for p in profs]
        classes = EbdClasse.query.filter(EbdClasse.id.in_(classes_ids), EbdClasse.status == "ativa").order_by(EbdClasse.nome).all() if classes_ids else []
    else:
        classes = []

    return render_template(
        "ebd/classes/minhas_classes.html",
        classes=classes,
        is_coordenador=is_coordenador
    )


# ==============================================================================
# 1. 📊 DASHBOARD DA ESCOLA DOMINICAL
# ==============================================================================
@ebd_bp.route("/")
@login_required
@permission_required("ebd", "view")
def dashboard():
    config = obter_ou_criar_config()
    periodo_ativo = EbdPeriodo.query.filter_by(status="em_andamento").order_by(EbdPeriodo.data_inicio.desc()).first()
    
    periodos = EbdPeriodo.query.order_by(EbdPeriodo.data_inicio.desc()).all()
    periodo_id = request.args.get("periodo_id", type=int)
    if periodo_id:
        periodo_selecionado = EbdPeriodo.query.get(periodo_id)
    else:
        periodo_selecionado = periodo_ativo or (periodos[0] if periodos else None)

    # Classes e métricas do período selecionado
    if periodo_selecionado:
        classes = EbdClasse.query.filter_by(periodo_id=periodo_selecionado.id, status="ativa").all()
        classes_ids = [c.id for c in classes]
    else:
        classes = []
        classes_ids = []

    # Totais Gerais
    total_classes = len(classes)
    total_professores = EbdProfessor.query.filter(EbdProfessor.classe_id.in_(classes_ids), EbdProfessor.status == "ativo").count() if classes_ids else 0
    total_matriculas_ativas = EbdMatricula.query.filter(EbdMatricula.classe_id.in_(classes_ids), EbdMatricula.status == "ativo").count() if classes_ids else 0
    
    # Aulas do período
    aulas = EbdAula.query.filter(EbdAula.classe_id.in_(classes_ids), EbdAula.status == "realizada").order_by(EbdAula.data_aula.desc()).all() if classes_ids else []
    total_aulas_realizadas = len(aulas)

    # Último domingo / aula realizada
    ultima_aula = aulas[0] if aulas else None
    data_ultima_aula = ultima_aula.data_aula if ultima_aula else None

    presencas_ultimo_domingo = 0
    faltas_ultimo_domingo = 0
    justificadas_ultimo_domingo = 0
    visitantes_ultimo_domingo = 0

    if data_ultima_aula:
        aulas_ultimo_domingo = [a for a in aulas if a.data_aula == data_ultima_aula]
        aula_ids_ultimo = [a.id for a in aulas_ultimo_domingo]
        if aula_ids_ultimo:
            freqs_ultimo = EbdFrequencia.query.filter(EbdFrequencia.aula_id.in_(aula_ids_ultimo)).all()
            for f in freqs_ultimo:
                if f.status_presenca == "presente":
                    presencas_ultimo_domingo += 1
                elif f.status_presenca == "falta":
                    faltas_ultimo_domingo += 1
                elif f.status_presenca == "falta_justificada":
                    justificadas_ultimo_domingo += 1
                elif f.status_presenca == "visitante":
                    visitantes_ultimo_domingo += 1

    # Taxa média de frequência geral do período
    total_registros_presenca = 0
    total_presentes_geral = 0
    if classes_ids:
        todas_aulas_ids = [a.id for a in aulas]
        if todas_aulas_ids:
            todas_freqs = EbdFrequencia.query.filter(EbdFrequencia.aula_id.in_(todas_aulas_ids)).all()
            total_registros_presenca = len(todas_freqs)
            total_presentes_geral = len([f for f in todas_freqs if f.status_presenca == "presente"])

    taxa_frequencia_geral = round((total_presentes_geral / total_registros_presenca * 100), 1) if total_registros_presenca > 0 else 0.0

    # Desempenho por Classe (para gráficos e ranking)
    classes_ranking = []
    for c in classes:
        aulas_c = [a.id for a in c.aulas if a.status == "realizada"]
        if aulas_c:
            freqs_c = EbdFrequencia.query.filter(EbdFrequencia.aula_id.in_(aulas_c)).all()
            p_c = len([f for f in freqs_c if f.status_presenca == "presente"])
            t_c = len(freqs_c)
            taxa_c = round((p_c / t_c * 100), 1) if t_c > 0 else 0.0
        else:
            taxa_c = 0.0
            p_c = 0
        classes_ranking.append({
            "classe": c,
            "taxa": taxa_c,
            "presentes": p_c,
            "matriculados": c.total_matriculados_ativos
        })
    classes_ranking.sort(key=lambda x: x["taxa"], reverse=True)

    # Evolução semanal de presença (últimos 8 domingos)
    datas_aulas_unicas = sorted(list({a.data_aula for a in aulas}))[-8:]
    labels_grafico = [d.strftime("%d/%m") for d in datas_aulas_unicas]
    dados_grafico_presentes = []
    dados_grafico_faltas = []

    for d in datas_aulas_unicas:
        aulas_data = [a.id for a in aulas if a.data_aula == d]
        freqs_data = EbdFrequencia.query.filter(EbdFrequencia.aula_id.in_(aulas_data)).all() if aulas_data else []
        dados_grafico_presentes.append(len([f for f in freqs_data if f.status_presenca == "presente"]))
        dados_grafico_faltas.append(len([f for f in freqs_data if f.status_presenca in ["falta", "falta_justificada"]]))

    # Alertas de Baixa Frequência (< 60% ou 3+ faltas seguidas)
    alunos_alerta = []
    if classes_ids and aulas:
        matriculas_ativas = EbdMatricula.query.filter(EbdMatricula.classe_id.in_(classes_ids), EbdMatricula.status == "ativo").all()
        for mat in matriculas_ativas:
            freqs_mat = EbdFrequencia.query.filter_by(matricula_id=mat.id).all()
            if freqs_mat:
                pres = len([f for f in freqs_mat if f.status_presenca == "presente"])
                taxa_aluno = round((pres / len(freqs_mat) * 100), 1)
                if taxa_aluno < 60.0 or len(freqs_mat) >= 3 and all(f.status_presenca in ["falta", "falta_justificada"] for f in freqs_mat[-3:]):
                    alunos_alerta.append({
                        "matricula": mat,
                        "membro": mat.membro,
                        "classe": mat.classe,
                        "taxa": taxa_aluno,
                        "total_faltas": len([f for f in freqs_mat if f.status_presenca in ["falta", "falta_justificada"]]),
                        "total_aulas": len(freqs_mat)
                    })

    return render_template(
        "ebd/dashboard.html",
        config=config,
        periodos=periodos,
        periodo_selecionado=periodo_selecionado,
        total_classes=total_classes,
        total_professores=total_professores,
        total_matriculas_ativas=total_matriculas_ativas,
        total_aulas_realizadas=total_aulas_realizadas,
        taxa_frequencia_geral=taxa_frequencia_geral,
        data_ultima_aula=data_ultima_aula,
        presencas_ultimo_domingo=presencas_ultimo_domingo,
        faltas_ultimo_domingo=faltas_ultimo_domingo,
        justificadas_ultimo_domingo=justificadas_ultimo_domingo,
        visitantes_ultimo_domingo=visitantes_ultimo_domingo,
        classes_ranking=classes_ranking,
        labels_grafico=labels_grafico,
        dados_grafico_presentes=dados_grafico_presentes,
        dados_grafico_faltas=dados_grafico_faltas,
        alunos_alerta=alunos_alerta[:6]
    )


# ==============================================================================
# 2. ⚙️ CONFIGURAÇÕES DA EBD
# ==============================================================================
@ebd_bp.route("/config", methods=["GET", "POST"])
@login_required
@permission_required("ebd", "edit")
def config_ebd():
    config = obter_ou_criar_config()
    form = EbdConfigForm(obj=config)
    
    membros = Member.query.filter_by(status="Ativo").order_by(Member.nome).all()
    form.coordenador_id.choices = [(0, "Nenhum coordenador selecionado")] + [(m.id, m.nome) for m in membros]

    if form.validate_on_submit():
        config.nome = form.nome.data
        config.descricao = sanitizar_html(form.descricao.data)
        config.dia_semana = form.dia_semana.data
        config.horario_inicio = form.horario_inicio.data
        config.horario_termino = form.horario_termino.data
        config.coordenador_id = form.coordenador_id.data if form.coordenador_id.data != 0 else None
        config.ativo = form.ativo.data
        
        db.session.commit()
        registrar_log_ebd(f"Atualizou configurações gerais da EBD: {config.nome}")
        flash("Configurações da Escola Dominical salvas com sucesso!", "success")
        return redirect(url_for("ebd.config_ebd"))

    if config.coordenador_id:
        form.coordenador_id.data = config.coordenador_id

    return render_template("ebd/config.html", form=form, config=config)


# ==============================================================================
# 3. 📅 PERÍODOS LETIVOS / TRIMESTRES
# ==============================================================================
@ebd_bp.route("/periodos")
@login_required
@permission_required("ebd", "view")
def listar_periodos():
    periodos = EbdPeriodo.query.order_by(EbdPeriodo.data_inicio.desc()).all()
    return render_template("ebd/periodos/listar_periodos.html", periodos=periodos)


@ebd_bp.route("/periodos/novo", methods=["GET", "POST"])
@login_required
@permission_required("ebd", "create")
def novo_periodo():
    form = EbdPeriodoForm()
    if form.validate_on_submit():
        periodo = EbdPeriodo(
            nome=form.nome.data,
            data_inicio=form.data_inicio.data,
            data_fim=form.data_fim.data,
            status=form.status.data,
            observacoes=sanitizar_html(form.observacoes.data)
        )
        db.session.add(periodo)
        db.session.commit()
        registrar_log_ebd(f"Cadastrou período letivo da EBD: {periodo.nome}")
        flash("Período letivo criado com sucesso!", "success")
        return redirect(url_for("ebd.listar_periodos"))
    return render_template("ebd/periodos/novo_periodo.html", form=form)


@ebd_bp.route("/periodos/<int:id>/editar", methods=["GET", "POST"])
@login_required
@permission_required("ebd", "edit")
def editar_periodo(id):
    periodo = EbdPeriodo.query.get_or_404(id)
    form = EbdPeriodoForm(obj=periodo)
    if form.validate_on_submit():
        periodo.nome = form.nome.data
        periodo.data_inicio = form.data_inicio.data
        periodo.data_fim = form.data_fim.data
        periodo.status = form.status.data
        periodo.observacoes = sanitizar_html(form.observacoes.data)
        db.session.commit()
        registrar_log_ebd(f"Editou período letivo da EBD: {periodo.nome}")
        flash("Período letivo atualizado com sucesso!", "success")
        return redirect(url_for("ebd.listar_periodos"))
    return render_template("ebd/periodos/editar_periodo.html", form=form, periodo=periodo)


@ebd_bp.route("/periodos/<int:id>/excluir", methods=["POST"])
@login_required
@permission_required("ebd", "delete")
def excluir_periodo(id):
    periodo = EbdPeriodo.query.get_or_404(id)
    nome = periodo.nome
    db.session.delete(periodo)
    db.session.commit()
    registrar_log_ebd(f"Excluiu período letivo da EBD: {nome}")
    flash("Período letivo excluído com sucesso!", "success")
    return redirect(url_for("ebd.listar_periodos"))


# ==============================================================================
# 4. 📚 CLASSES / TURMAS
# ==============================================================================
@ebd_bp.route("/classes")
@login_required
@permission_required("ebd", "view")
def listar_classes():
    periodos = EbdPeriodo.query.order_by(EbdPeriodo.data_inicio.desc()).all()
    periodo_id = request.args.get("periodo_id", type=int)
    
    query = EbdClasse.query
    if periodo_id:
        query = query.filter_by(periodo_id=periodo_id)
    
    classes = query.order_by(EbdClasse.nome).all()
    return render_template("ebd/classes/listar_classes.html", classes=classes, periodos=periodos, periodo_selecionado_id=periodo_id)


@ebd_bp.route("/classes/nova", methods=["GET", "POST"])
@login_required
@permission_required("ebd", "create")
def nova_classe():
    form = EbdClasseForm()
    periodos = EbdPeriodo.query.order_by(EbdPeriodo.data_inicio.desc()).all()
    form.periodo_id.choices = [(p.id, f"{p.nome} ({p.status.capitalize()})") for p in periodos]

    if form.validate_on_submit():
        classe = EbdClasse(
            nome=form.nome.data,
            periodo_id=form.periodo_id.data,
            faixa_etaria=form.faixa_etaria.data,
            sala=form.sala.data,
            capacidade=form.capacidade.data,
            status=form.status.data,
            descricao=sanitizar_html(form.descricao.data)
        )
        db.session.add(classe)
        db.session.commit()
        registrar_log_ebd(f"Criou classe da EBD: {classe.nome}")
        flash("Classe cadastrada com sucesso!", "success")
        return redirect(url_for("ebd.listar_classes"))

    return render_template("ebd/classes/nova_classe.html", form=form)


@ebd_bp.route("/classes/<int:id>")
@login_required
@permission_required("ebd", "view")
def detalhe_classe(id):
    classe = EbdClasse.query.get_or_404(id)
    if not usuario_pode_gerenciar_classe(classe.id):
        flash("Acesso restrito: você só possui permissão para acessar os detalhes e chamadas das suas próprias classes.", "warning")
        return redirect(url_for("ebd.minhas_classes"))

    matriculas = [m for m in classe.matriculas if m.status == "ativo"]
    professores = [p for p in classe.professores if p.status == "ativo"]
    aulas = EbdAula.query.filter_by(classe_id=classe.id).order_by(EbdAula.data_aula.desc()).all()

    # Cálculo da taxa de presença da classe
    todas_aulas_ids = [a.id for a in aulas if a.status == "realizada"]
    if todas_aulas_ids:
        freqs = EbdFrequencia.query.filter(EbdFrequencia.aula_id.in_(todas_aulas_ids)).all()
        presentes = len([f for f in freqs if f.status_presenca == "presente"])
        taxa = round((presentes / len(freqs) * 100), 1) if freqs else 0.0
    else:
        taxa = 0.0

    return render_template(
        "ebd/classes/detalhe_classe.html",
        classe=classe,
        matriculas=matriculas,
        professores=professores,
        aulas=aulas,
        taxa_frequencia=taxa
    )


@ebd_bp.route("/classes/<int:id>/editar", methods=["GET", "POST"])
@login_required
@permission_required("ebd", "edit")
def editar_classe(id):
    classe = EbdClasse.query.get_or_404(id)
    form = EbdClasseForm(obj=classe)
    periodos = EbdPeriodo.query.order_by(EbdPeriodo.data_inicio.desc()).all()
    form.periodo_id.choices = [(p.id, f"{p.nome} ({p.status.capitalize()})") for p in periodos]

    if form.validate_on_submit():
        classe.nome = form.nome.data
        classe.periodo_id = form.periodo_id.data
        classe.faixa_etaria = form.faixa_etaria.data
        classe.sala = form.sala.data
        classe.capacidade = form.capacidade.data
        classe.status = form.status.data
        classe.descricao = sanitizar_html(form.descricao.data)
        db.session.commit()
        registrar_log_ebd(f"Editou classe da EBD: {classe.nome}")
        flash("Classe atualizada com sucesso!", "success")
        return redirect(url_for("ebd.detalhe_classe", id=classe.id))

    return render_template("ebd/classes/editar_classe.html", form=form, classe=classe)


@ebd_bp.route("/classes/<int:id>/excluir", methods=["POST"])
@login_required
@permission_required("ebd", "delete")
def excluir_classe(id):
    classe = EbdClasse.query.get_or_404(id)
    nome = classe.nome
    db.session.delete(classe)
    db.session.commit()
    registrar_log_ebd(f"Excluiu classe da EBD: {nome}")
    flash("Classe excluída com sucesso!", "success")
    return redirect(url_for("ebd.listar_classes"))


# ==============================================================================
# 5. 👨‍🏫 PROFESSORES
# ==============================================================================
@ebd_bp.route("/professores")
@login_required
@permission_required("ebd", "view")
def listar_professores():
    professores = EbdProfessor.query.order_by(EbdProfessor.classe_id).all()
    return render_template("ebd/professores/listar_professores.html", professores=professores)


@ebd_bp.route("/professores/novo", methods=["GET", "POST"])
@login_required
@permission_required("ebd", "create")
def vincular_professor():
    form = EbdProfessorForm()
    membros = Member.query.filter_by(status="Ativo").order_by(Member.nome).all()
    classes = EbdClasse.query.filter_by(status="ativa").order_by(EbdClasse.nome).all()
    
    form.membro_id.choices = [(m.id, m.nome) for m in membros]
    form.classe_id.choices = [(c.id, f"{c.nome} ({c.periodo.nome})") for c in classes]

    classe_pre_id = request.args.get("classe_id", type=int)
    if request.method == "GET" and classe_pre_id:
        form.classe_id.data = classe_pre_id

    if form.validate_on_submit():
        # Verifica se já está vinculado nessa classe
        existente = EbdProfessor.query.filter_by(
            classe_id=form.classe_id.data,
            membro_id=form.membro_id.data,
            status="ativo"
        ).first()

        if existente:
            flash("Este professor já está vinculado a esta classe!", "warning")
            return redirect(url_for("ebd.vincular_professor"))

        vinculo = EbdProfessor(
            classe_id=form.classe_id.data,
            membro_id=form.membro_id.data,
            cargo=form.cargo.data,
            status=form.status.data,
            data_inicio=form.data_inicio.data or date.today(),
            data_fim=form.data_fim.data
        )
        db.session.add(vinculo)
        db.session.commit()
        registrar_log_ebd(f"Vinculou professor ID {vinculo.membro_id} à classe ID {vinculo.classe_id}")
        flash("Professor vinculado com sucesso!", "success")
        return redirect(url_for("ebd.detalhe_classe", id=vinculo.classe_id))

    return render_template("ebd/professores/novo_professor.html", form=form)


@ebd_bp.route("/professores/<int:id>/desvincular", methods=["POST"])
@login_required
@permission_required("ebd", "delete")
def desvincular_professor(id):
    vinculo = EbdProfessor.query.get_or_404(id)
    classe_id = vinculo.classe_id
    vinculo.status = "inativo"
    vinculo.data_fim = date.today()
    db.session.commit()
    registrar_log_ebd(f"Desvinculou professor ID {vinculo.membro_id} da classe ID {classe_id}")
    flash("Vínculo do professor encerrado com sucesso!", "info")
    return redirect(url_for("ebd.detalhe_classe", id=classe_id))


# ==============================================================================
# 6. 🎓 MATRÍCULAS E ALUNOS
# ==============================================================================
@ebd_bp.route("/matriculas")
@login_required
@permission_required("ebd", "view")
def listar_matriculas():
    page = request.args.get("page", 1, type=int)
    termo = request.args.get("q", "", type=str)
    classe_id = request.args.get("classe_id", type=int)

    classes = EbdClasse.query.order_by(EbdClasse.nome).all()

    query = EbdMatricula.query.join(Member)
    if classe_id:
        query = query.filter(EbdMatricula.classe_id == classe_id)
    if termo:
        query = query.filter(Member.nome.ilike(f"%{termo}%"))

    matriculas = query.order_by(EbdMatricula.status, Member.nome).paginate(page=page, per_page=15)
    return render_template("ebd/matriculas/listar_matriculas.html", matriculas=matriculas, classes=classes, classe_selecionada_id=classe_id, termo=termo)


@ebd_bp.route("/matriculas/nova", methods=["GET", "POST"])
@login_required
@permission_required("ebd", "create")
def nova_matricula():
    form = EbdMatriculaForm()
    membros = Member.query.filter_by(status="Ativo").order_by(Member.nome).all()
    classes = EbdClasse.query.filter_by(status="ativa").order_by(EbdClasse.nome).all()

    form.membro_id.choices = [(m.id, m.nome) for m in membros]
    form.classe_id.choices = [(c.id, f"{c.nome} ({c.periodo.nome})") for c in classes]

    classe_pre_id = request.args.get("classe_id", type=int)
    if request.method == "GET" and classe_pre_id:
        form.classe_id.data = classe_pre_id

    if form.validate_on_submit():
        # Impede matrícula ativa duplicada na mesma classe
        ja_matriculado = EbdMatricula.query.filter_by(
            classe_id=form.classe_id.data,
            membro_id=form.membro_id.data,
            status="ativo"
        ).first()

        if ja_matriculado:
            flash("Este aluno já está matriculado ativamente nesta classe!", "warning")
            return redirect(url_for("ebd.nova_matricula", classe_id=form.classe_id.data))

        matricula = EbdMatricula(
            classe_id=form.classe_id.data,
            membro_id=form.membro_id.data,
            data_matricula=form.data_matricula.data or date.today(),
            status=form.status.data,
            observacoes=sanitizar_html(form.observacoes.data)
        )
        db.session.add(matricula)
        db.session.commit()
        registrar_log_ebd(f"Matriculou aluno ID {matricula.membro_id} na classe ID {matricula.classe_id}")
        flash("Aluno matriculado com sucesso na EBD!", "success")
        return redirect(url_for("ebd.detalhe_classe", id=matricula.classe_id))

    return render_template("ebd/matriculas/nova_matricula.html", form=form)


@ebd_bp.route("/matriculas/<int:id>/transferir", methods=["GET", "POST"])
@login_required
@permission_required("ebd", "edit")
def transferir_matricula(id):
    matricula_atual = EbdMatricula.query.get_or_404(id)
    form = EbdTransferenciaForm()
    
    classes_disponiveis = EbdClasse.query.filter(
        EbdClasse.id != matricula_atual.classe_id,
        EbdClasse.status == "ativa"
    ).all()
    form.nova_classe_id.choices = [(c.id, f"{c.nome} ({c.periodo.nome})") for c in classes_disponiveis]

    if form.validate_on_submit():
        # 1. Encerra matrícula anterior
        matricula_atual.status = "transferido"
        matricula_atual.data_saida = date.today()
        matricula_atual.motivo_saida = form.motivo_saida.data or "Transferência de classe"
        
        # 2. Cria nova matrícula na nova classe
        nova_mat = EbdMatricula(
            classe_id=form.nova_classe_id.data,
            membro_id=matricula_atual.membro_id,
            data_matricula=date.today(),
            status="ativo",
            observacoes=f"Transferido da classe {matricula_atual.classe.nome}. {form.observacoes.data or ''}"
        )
        db.session.add(nova_mat)
        db.session.commit()
        
        registrar_log_ebd(f"Transferiu aluno ID {matricula_atual.membro_id} para a classe ID {nova_mat.classe_id}")
        flash(f"Aluno transferido com sucesso para a classe {nova_mat.classe.nome}!", "success")
        return redirect(url_for("ebd.detalhe_classe", id=nova_mat.classe_id))

    return render_template("ebd/matriculas/transferir_matricula.html", form=form, matricula=matricula_atual)


@ebd_bp.route("/matriculas/<int:id>/cancelar", methods=["POST"])
@login_required
@permission_required("ebd", "delete")
def cancelar_matricula(id):
    matricula = EbdMatricula.query.get_or_404(id)
    classe_id = matricula.classe_id
    matricula.status = "desligado"
    matricula.data_saida = date.today()
    matricula.motivo_saida = request.form.get("motivo_saida", "Desligamento voluntário")
    db.session.commit()
    registrar_log_ebd(f"Desligou matrícula ID {matricula.id} do aluno {matricula.membro.nome}")
    flash("Matrícula encerrada com sucesso.", "info")
    return redirect(url_for("ebd.detalhe_classe", id=classe_id))


@ebd_bp.route("/alunos/<int:membro_id>/historico")
@login_required
@permission_required("ebd", "view")
def historico_aluno(membro_id):
    membro = Member.query.get_or_404(membro_id)
    matriculas = EbdMatricula.query.filter_by(membro_id=membro.id).order_by(EbdMatricula.data_matricula.desc()).all()
    matricula_ids = [m.id for m in matriculas]

    frequencias = EbdFrequencia.query.filter(EbdFrequencia.matricula_id.in_(matricula_ids)).join(EbdAula).order_by(EbdAula.data_aula.desc()).all() if matricula_ids else []

    total_aulas = len(frequencias)
    total_presencas = len([f for f in frequencias if f.status_presenca == "presente"])
    total_faltas = len([f for f in frequencias if f.status_presenca == "falta"])
    total_justificadas = len([f for f in frequencias if f.status_presenca == "falta_justificada"])
    taxa_presenca = round((total_presencas / total_aulas * 100), 1) if total_aulas > 0 else 0.0

    return render_template(
        "ebd/matriculas/historico_aluno.html",
        membro=membro,
        matriculas=matriculas,
        frequencias=frequencias,
        total_aulas=total_aulas,
        total_presencas=total_presencas,
        total_faltas=total_faltas,
        total_justificadas=total_justificadas,
        taxa_presenca=taxa_presenca
    )


# ==============================================================================
# 7. 📖 AULAS E LIÇÕES
# ==============================================================================
@ebd_bp.route("/aulas")
@login_required
@permission_required("ebd", "view")
def listar_aulas():
    page = request.args.get("page", 1, type=int)
    classe_id = request.args.get("classe_id", type=int)
    
    classes = EbdClasse.query.order_by(EbdClasse.nome).all()
    query = EbdAula.query
    if classe_id:
        query = query.filter_by(classe_id=classe_id)
        
    aulas = query.order_by(EbdAula.data_aula.desc()).paginate(page=page, per_page=12)
    return render_template("ebd/aulas/listar_aulas.html", aulas=aulas, classes=classes, classe_selecionada_id=classe_id)


@ebd_bp.route("/aulas/nova", methods=["GET", "POST"])
@login_required
@permission_required("ebd", "create")
def nova_aula():
    form = EbdAulaForm()
    classes = EbdClasse.query.filter_by(status="ativa").order_by(EbdClasse.nome).all()
    membros = Member.query.filter_by(status="Ativo").order_by(Member.nome).all()

    form.classe_id.choices = [(c.id, f"{c.nome} ({c.periodo.nome})") for c in classes]
    form.professor_id.choices = [(0, "Selecione o professor...")] + [(m.id, m.nome) for m in membros]

    classe_pre_id = request.args.get("classe_id", type=int)
    if request.method == "GET" and classe_pre_id:
        form.classe_id.data = classe_pre_id
        classe_obj = EbdClasse.query.get(classe_pre_id)
        if classe_obj and classe_obj.professor_principal:
            form.professor_id.data = classe_obj.professor_principal.id
        form.data_aula.data = date.today()

    if form.validate_on_submit():
        aula = EbdAula(
            classe_id=form.classe_id.data,
            professor_id=form.professor_id.data if form.professor_id.data != 0 else None,
            data_aula=form.data_aula.data,
            numero_licao=form.numero_licao.data,
            tema=form.tema.data,
            resumo_conteudo=sanitizar_html(form.resumo_conteudo.data),
            status=form.status.data,
            observacoes=sanitizar_html(form.observacoes.data)
        )
        db.session.add(aula)
        db.session.commit()
        registrar_log_ebd(f"Criou aula de EBD: {aula.tema} ({aula.data_aula})")
        flash("Aula registrada com sucesso! Você pode realizar a chamada agora.", "success")
        return redirect(url_for("ebd.realizar_chamada", id=aula.id))

    return render_template("ebd/aulas/nova_aula.html", form=form)


@ebd_bp.route("/aulas/<int:id>/editar", methods=["GET", "POST"])
@login_required
@permission_required("ebd", "edit")
def editar_aula(id):
    aula = EbdAula.query.get_or_404(id)
    form = EbdAulaForm(obj=aula)
    classes = EbdClasse.query.order_by(EbdClasse.nome).all()
    membros = Member.query.filter_by(status="Ativo").order_by(Member.nome).all()

    form.classe_id.choices = [(c.id, f"{c.nome} ({c.periodo.nome})") for c in classes]
    form.professor_id.choices = [(0, "Selecione o professor...")] + [(m.id, m.nome) for m in membros]

    if form.validate_on_submit():
        aula.classe_id = form.classe_id.data
        aula.professor_id = form.professor_id.data if form.professor_id.data != 0 else None
        aula.data_aula = form.data_aula.data
        aula.numero_licao = form.numero_licao.data
        aula.tema = form.tema.data
        aula.resumo_conteudo = sanitizar_html(form.resumo_conteudo.data)
        aula.status = form.status.data
        aula.observacoes = sanitizar_html(form.observacoes.data)
        db.session.commit()
        registrar_log_ebd(f"Editou aula de EBD ID {aula.id}: {aula.tema}")
        flash("Aula atualizada com sucesso!", "success")
        return redirect(url_for("ebd.realizar_chamada", id=aula.id))

    if aula.professor_id:
        form.professor_id.data = aula.professor_id

    return render_template("ebd/aulas/editar_aula.html", form=form, aula=aula)


@ebd_bp.route("/aulas/<int:id>/excluir", methods=["POST"])
@login_required
@permission_required("ebd", "delete")
def excluir_aula(id):
    aula = EbdAula.query.get_or_404(id)
    classe_id = aula.classe_id
    db.session.delete(aula)
    db.session.commit()
    registrar_log_ebd(f"Excluiu aula de EBD ID {id}")
    flash("Aula excluída com sucesso.", "success")
    return redirect(url_for("ebd.detalhe_classe", id=classe_id))


# ==============================================================================
# 8. ✅ CHAMADA E FREQUÊNCIA ÁGIL (DESKTOP & MOBILE-FIRST)
# ==============================================================================
@ebd_bp.route("/aulas/<int:id>/chamada", methods=["GET", "POST"])
@login_required
@permission_required("ebd", "frequencia")
def realizar_chamada(id):
    aula = EbdAula.query.get_or_404(id)
    if not usuario_pode_gerenciar_classe(aula.classe_id):
        flash("Acesso não autorizado para gerenciar a chamada desta classe.", "danger")
        return redirect(url_for("ebd.minhas_classes"))

    classe = aula.classe
    matriculas_ativas = EbdMatricula.query.filter_by(classe_id=classe.id, status="ativo").join(Member).order_by(Member.nome).all()

    # Busca registros de frequência já existentes para esta aula
    frequencias_existentes = {f.matricula_id: f for f in aula.frequencias}

    if request.method == "POST":
        operador_nome = getattr(current_user, "nome", "Operador")
        
        for mat in matriculas_ativas:
            status_param = request.form.get(f"status_{mat.id}", "presente")
            motivo_param = request.form.get(f"motivo_{mat.id}", "")
            justificativa_param = request.form.get(f"justificativa_{mat.id}", "")
            obs_param = request.form.get(f"obs_{mat.id}", "")

            freq_obj = frequencias_existentes.get(mat.id)
            if not freq_obj:
                freq_obj = EbdFrequencia(
                    aula_id=aula.id,
                    matricula_id=mat.id,
                    status_presenca=status_param,
                    motivo_falta=motivo_param if status_param == "falta_justificada" else None,
                    justificativa=justificativa_param if status_param == "falta_justificada" else None,
                    observacao_aluno=obs_param,
                    registrado_por=operador_nome
                )
                db.session.add(freq_obj)
            else:
                freq_obj.status_presenca = status_param
                freq_obj.motivo_falta = motivo_param if status_param == "falta_justificada" else None
                freq_obj.justificativa = justificativa_param if status_param == "falta_justificada" else None
                freq_obj.observacao_aluno = obs_param
                freq_obj.registrado_por = operador_nome

        aula.status = "realizada"
        db.session.commit()
        registrar_log_ebd(f"Gravou chamada da aula '{aula.tema}' ({classe.nome} - {aula.data_aula.strftime('%d/%m/%Y')})")
        flash("Chamada gravada e sincronizada com sucesso!", "success")
        return redirect(url_for("ebd.realizar_chamada", id=aula.id))

    return render_template(
        "ebd/chamada/chamada.html",
        aula=aula,
        classe=classe,
        matriculas=matriculas_ativas,
        frequencias=frequencias_existentes
    )


# ==============================================================================
# 9. 📈 RELATÓRIOS E MAPA DE FREQUÊNCIA (PLANILHA)
# ==============================================================================
@ebd_bp.route("/relatorios/mapa-frequencia")
@login_required
@permission_required("ebd", "view")
def mapa_frequencia():
    classes = EbdClasse.query.filter_by(status="ativa").order_by(EbdClasse.nome).all()
    classe_id = request.args.get("classe_id", type=int)
    
    classe_selecionada = None
    datas_aulas = []
    matriz_alunos = []

    if classe_id:
        classe_selecionada = EbdClasse.query.get_or_404(classe_id)
        aulas = EbdAula.query.filter_by(classe_id=classe_selecionada.id, status="realizada").order_by(EbdAula.data_aula).all()
        datas_aulas = [a.data_aula for a in aulas]
        aula_map = {a.data_aula: a.id for a in aulas}

        matriculas = EbdMatricula.query.filter_by(classe_id=classe_selecionada.id, status="ativo").join(Member).order_by(Member.nome).all()

        for mat in matriculas:
            freqs = {f.aula.data_aula: f for f in mat.frequencias if f.aula.status == "realizada"}
            linha_presencas = []
            total_p = 0
            for d in datas_aulas:
                f_obj = freqs.get(d)
                if f_obj:
                    st = f_obj.status_presenca
                    if st == "presente":
                        total_p += 1
                        linha_presencas.append({"status": "P", "badge": "bg-success", "tooltip": "Presente"})
                    elif st == "falta_justificada":
                        linha_presencas.append({"status": "J", "badge": "bg-warning text-dark", "tooltip": f"Justificada: {f_obj.motivo_falta or ''}"})
                    elif st == "falta":
                        linha_presencas.append({"status": "F", "badge": "bg-danger", "tooltip": "Falta"})
                    else:
                        linha_presencas.append({"status": "V", "badge": "bg-info", "tooltip": "Visitante"})
                else:
                    linha_presencas.append({"status": "-", "badge": "bg-light text-muted border", "tooltip": "Sem registro"})

            taxa = round((total_p / len(datas_aulas) * 100), 1) if datas_aulas else 0.0
            matriz_alunos.append({
                "membro": mat.membro,
                "matricula": mat,
                "frequencias": linha_presencas,
                "total_presencas": total_p,
                "taxa": taxa
            })

    return render_template(
        "ebd/relatorios/mapa_frequencia.html",
        classes=classes,
        classe_selecionada=classe_selecionada,
        datas_aulas=datas_aulas,
        matriz_alunos=matriz_alunos
    )


@ebd_bp.route("/relatorios/geral")
@login_required
@permission_required("ebd", "view")
def relatorio_geral():
    periodo_ativo = EbdPeriodo.query.filter_by(status="em_andamento").first()
    classes = EbdClasse.query.all()
    matriculas_total = EbdMatricula.query.count()
    professores_total = EbdProfessor.query.filter_by(status="ativo").count()
    aulas_total = EbdAula.query.filter_by(status="realizada").count()
    frequencias_total = EbdFrequencia.query.count()
    presentes_total = EbdFrequencia.query.filter_by(status_presenca="presente").count()

    taxa_global = round((presentes_total / frequencias_total * 100), 1) if frequencias_total > 0 else 0.0

    return render_template(
        "ebd/relatorios/relatorio_geral.html",
        periodo_ativo=periodo_ativo,
        classes=classes,
        matriculas_total=matriculas_total,
        professores_total=professores_total,
        aulas_total=aulas_total,
        taxa_global=taxa_global
    )
