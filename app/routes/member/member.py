import os
from datetime import datetime, date, timedelta
import re
from collections import Counter

from flask import (
    Blueprint, render_template, request, redirect, url_for,
    flash, current_app, make_response, Response, jsonify
)
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from werkzeug.datastructures import CombinedMultiDict
from sqlalchemy import func
try:
    from weasyprint import HTML  # ➕ para gerar PDF
except (ImportError, OSError):
    HTML = None
from werkzeug.datastructures import FileStorage

from utils.pagination import paginate_query
from utils.sanitizer import sanitizar_html
from app.models import Member, PublicLink, User, Permission, UserPermission        # 👈 importa os modelos
from app.models.log import Log, registrar_log    # 👈 modelo de log
from app.routes.member.forms import MemberForm   # 👈 formulário
from app.decorators import permission_required 	 # 👈 importa o decorator
from app.extensions import db


member_bp = Blueprint('member', __name__, url_prefix="/membros")


def gerar_proximo_numero_carteira() -> str:
    """Gera o próximo número de carteirinha sequencial a partir de 00001 evitando qualquer duplicidade."""
    membros = Member.query.filter(Member.numero_carteira.isnot(None)).all()
    maior_num = 0
    for m in membros:
        if not m.numero_carteira:
            continue
        match = re.search(r'(\d+)', str(m.numero_carteira).strip())
        if match:
            try:
                val = int(match.group(1))
                if val > maior_num:
                    maior_num = val
            except ValueError:
                pass

    proximo = maior_num + 1 if maior_num >= 1 else 1
    novo_numero = f"{proximo:05d}"

    # Garante ausência total de duplicidades no banco de dados
    while Member.query.filter_by(numero_carteira=novo_numero).first() is not None:
        proximo += 1
        novo_numero = f"{proximo:05d}"

    return novo_numero


def calcular_validade_carteira(data_base=None) -> date:
    """Calcula a validade fixa em 365 dias a partir da data de criação/cadastro."""
    if not data_base:
        data_base = date.today()
    return data_base + timedelta(days=365)

# -----------------------------
# 📋 Listagem e Busca de Membros com Paginação
# -----------------------------
@member_bp.route("/", methods=["GET"])
@login_required
@permission_required("membros", "view")
def listar_membros():
    page = request.args.get("page", 1, type=int)
    termo = request.args.get("q", "").strip()
    status_filtro = request.args.get("status", "Ativo")

    query = Member.query

    # Filtro por status (padrão: Ativo)
    if status_filtro == "Ativo":
        query = query.filter((Member.status.is_(None)) | (Member.status == "Ativo"))
    elif status_filtro == "Transferido":
        query = query.filter(Member.status == "Transferido")
    elif status_filtro == "Inativo":
        query = query.filter(Member.status == "Inativo")
    # Se for "Todos" ou vazio, não aplica filtro de status

    if termo:
        query = query.filter(
            (Member.nome.ilike(f"%{termo}%")) |
            (Member.email.ilike(f"%{termo}%")) |
            (Member.funcao.ilike(f"%{termo}%"))
        )

    membros = query.order_by(Member.nome.asc()).paginate(page=page, per_page=10, error_out=False)

    # Busca o último link de visitante ativo
    visitante_link = PublicLink.query.filter_by(tipo="visitante", ativo=True).order_by(PublicLink.data_criacao.desc()).first()
    if not visitante_link:
        novo_hash = PublicLink.gerar_hash()
        visitante_link = PublicLink(tipo="visitante", hash=novo_hash)
        db.session.add(visitante_link)
        db.session.commit()

    visitante_link_url = url_for("member.cadastro_visitante", hash=visitante_link.hash, _external=True)

    return render_template(
        "membros/listar_membros.html",
        membros=membros,
        visitante_link_url=visitante_link_url,
        termo=termo,
        status_filtro=status_filtro
    )


# -----------------------------
# 🔍 Buscar Membros
# -----------------------------
@member_bp.route("/buscar", methods=["GET"])
@login_required   # 👈 protege a rota
@permission_required("membros", "view")
def buscar_membros():
    termo = request.args.get("q", "").strip()
    status_filtro = request.args.get("status", "Ativo")
    page = request.args.get("page", 1, type=int)

    query = Member.query

    # Filtro por status
    if status_filtro == "Ativo":
        query = query.filter((Member.status.is_(None)) | (Member.status == "Ativo"))
    elif status_filtro == "Transferido":
        query = query.filter(Member.status == "Transferido")
    elif status_filtro == "Inativo":
        query = query.filter(Member.status == "Inativo")

    if termo:
        query = query.filter(
            (Member.nome.ilike(f"%{termo}%")) |
            (Member.email.ilike(f"%{termo}%")) |
            (Member.funcao.ilike(f"%{termo}%"))
        )

    query = query.order_by(Member.nome.asc())
    membros = query.paginate(page=page, per_page=10)

    # Busca o último link de visitante ativo
    visitante_link = PublicLink.query.filter_by(tipo="visitante", ativo=True).order_by(PublicLink.data_criacao.desc()).first()
    visitante_link_url = url_for("member.cadastro_visitante", hash=visitante_link.hash, _external=True) if visitante_link else ""

    if termo:
        if membros.total == 0:
            flash("Nenhum membro corresponde ao termo pesquisado", "warning")
        elif membros.total == 1:
            flash("1 membro encontrado", "info")
        else:
            flash(f"{membros.total} membro(s) encontrado(s)", "info")

    return render_template(
        "membros/listar_membros.html",
        membros=membros,
        visitante_link_url=visitante_link_url,
        termo=termo,
        status_filtro=status_filtro
    )
    

# -----------------------------
# ➕ Cadastro de Membros
# -----------------------------
@member_bp.route("/cadastro", methods=["GET", "POST"])
@login_required
@permission_required("membros", "create")
def cadastro_membro():
    form = MemberForm()

    # No GET, pré-preenche o próximo número de carteira sequencial e a validade fixa em 365 dias
    if request.method == "GET":
        if not form.numero_carteira.data:
            form.numero_carteira.data = gerar_proximo_numero_carteira()
        if not form.validade.data:
            dt_base = form.data_cadastro.data or date.today()
            form.validade.data = calcular_validade_carteira(dt_base)

    if request.method == "POST" and form.validate_on_submit():
        existente = None
        if form.cpf.data:
            existente = Member.query.filter(Member.cpf == form.cpf.data).first()
        elif form.nome.data and form.data_nascimento.data:
            existente = Member.query.filter(
                (Member.nome == form.nome.data) &
                (Member.data_nascimento == form.data_nascimento.data)
            ).first()

        if existente:
            flash("Já existe um membro cadastrado com esses dados!", "danger")
            return render_template("membros/cadastro_membro.html", form=form)

        # Determina número da carteira automático
        carteira_final = (form.numero_carteira.data or "").strip()
        if not carteira_final:
            carteira_final = gerar_proximo_numero_carteira()

        # Validade fixa em 365 dias a partir da data de cadastro/criação
        dt_base = form.data_cadastro.data or date.today()
        validade_final = form.validade.data or calcular_validade_carteira(dt_base)

        membro = Member(
            nome=form.nome.data,
            data_nascimento=form.data_nascimento.data,
            sexo=form.sexo.data,
            estado_civil=form.estado_civil.data,
            conjuge=form.conjuge.data if form.estado_civil.data == "Casado" else None,
            telefone=form.telefone.data,
            is_whatsapp=bool(form.is_whatsapp.data),
            email=form.email.data,
            endereco=form.endereco.data,
            bairro=form.bairro.data,
            cep=form.cep.data,
            batizado=form.batizado.data,
            dizimista=form.dizimista.data,
            data_batismo=form.data_batismo.data,
            funcao=form.funcao.data,
            observacoes=sanitizar_html(form.observacoes.data),
            status=form.status.data or "Ativo",
            nacionalidade=form.nacionalidade.data,
            naturalidade=form.naturalidade.data,
            rg=form.rg.data,
            cpf=form.cpf.data,
            pai=form.pai.data,
            mae=form.mae.data,
            filiacao=form.filiacao.data,
            numero_carteira=carteira_final,
            igreja_local=form.igreja_local.data,
            validade=validade_final,
            data_cadastro=form.data_cadastro.data,
            data_conversao=form.data_conversao.data,
            data_saida=None if (form.status.data or "Ativo") == "Ativo" else form.data_saida.data
        )

        # Upload da foto
        foto_file = form.foto.data
        if foto_file:
            filename = secure_filename(foto_file.filename)
            upload_folder = current_app.config['UPLOAD_FOLDER']
            os.makedirs(upload_folder, exist_ok=True)
            foto_path = os.path.join(upload_folder, filename)
            foto_file.save(foto_path)
            membro.foto = f"uploads/{filename}"

        db.session.add(membro)
        db.session.commit()
        flash(f"Membro {membro.nome} cadastrado com sucesso! Carteira Nº {membro.numero_carteira}", "success")

        # Registrar log com nome do membro
        registrar_log(current_user.nome, f"Cadastro de Membro: {membro.nome} (Carteira: {membro.numero_carteira})")

        return redirect(url_for("member.listar_membros"))

    # ⚠️ Se chegou aqui, houve erro de validação
    if request.method == "POST":
        for field, errors in form.errors.items():
            for error in errors:
                flash(error, "danger")

    return render_template("membros/cadastro_membro.html", form=form)


# -----------------------------
# ✏️ Edição de Membros
# -----------------------------
@member_bp.route("/editar/<int:id>", methods=["GET", "POST"])
@login_required
@permission_required("membros", "edit")
def editar_membro(id):
    membro = Member.query.get_or_404(id)
    form = MemberForm(obj=membro)

    if request.method == "GET":
        form.batizado.data = membro.batizado
        form.dizimista.data = membro.dizimista
        form.is_whatsapp.data = bool(membro.is_whatsapp)
        # Se membro ainda não possuir carteira ou validade, sugere preenchimento automático
        if not form.numero_carteira.data:
            form.numero_carteira.data = gerar_proximo_numero_carteira()
        if not form.validade.data:
            dt_base = membro.data_cadastro or date.today()
            form.validade.data = calcular_validade_carteira(dt_base)

    if request.method == "POST" and form.validate_on_submit():
        carteira_final = (form.numero_carteira.data or "").strip()
        if not carteira_final:
            carteira_final = membro.numero_carteira or gerar_proximo_numero_carteira()

        dt_base = form.data_cadastro.data or membro.data_cadastro or date.today()
        validade_final = form.validade.data or membro.validade or calcular_validade_carteira(dt_base)

        membro.nome = form.nome.data
        membro.data_nascimento = form.data_nascimento.data
        membro.sexo = form.sexo.data
        membro.estado_civil = form.estado_civil.data
        membro.conjuge = form.conjuge.data if form.estado_civil.data == "Casado" else None
        membro.telefone = form.telefone.data
        membro.is_whatsapp = bool(form.is_whatsapp.data)
        membro.email = form.email.data
        membro.endereco = form.endereco.data
        membro.bairro = form.bairro.data
        membro.cep = form.cep.data
        membro.batizado = form.batizado.data
        membro.dizimista = form.dizimista.data
        membro.data_batismo = form.data_batismo.data
        membro.funcao = form.funcao.data
        membro.observacoes = sanitizar_html(form.observacoes.data)
        membro.status = form.status.data
        membro.nacionalidade = form.nacionalidade.data
        membro.naturalidade = form.naturalidade.data
        membro.rg = form.rg.data
        membro.cpf = form.cpf.data
        membro.pai = form.pai.data
        membro.mae = form.mae.data
        membro.filiacao = form.filiacao.data
        membro.numero_carteira = carteira_final
        membro.igreja_local = form.igreja_local.data
        membro.validade = validade_final
        membro.data_cadastro = form.data_cadastro.data or membro.data_cadastro
        membro.data_conversao = form.data_conversao.data or membro.data_conversao
        if membro.status == "Ativo":
            membro.data_saida = None
        else:
            membro.data_saida = form.data_saida.data if form.data_saida.data else None

        # Upload da foto (somente se for um arquivo válido)
        foto_file = form.foto.data
        if isinstance(foto_file, FileStorage) and foto_file.filename:
            filename = secure_filename(foto_file.filename)
            upload_folder = current_app.config['UPLOAD_FOLDER']
            os.makedirs(upload_folder, exist_ok=True)
            foto_path = os.path.join(upload_folder, filename)
            foto_file.save(foto_path)
            membro.foto = f"uploads/{filename}"

        if "remover_foto" in request.form:
            membro.foto = None

        db.session.commit()
        flash(f"Membro {membro.nome} atualizado com sucesso!", "success")

        # Registrar log com nome do membro
        registrar_log(current_user.nome, f"Edição de Membro: {membro.nome}")

        return redirect(url_for("member.listar_membros"))

    # ⚠️ Se chegou aqui, houve erro de validação (ex.: imagem inválida)
    if request.method == "POST":
        for field, errors in form.errors.items():
            for error in errors:
                flash(error, "danger")

    return render_template("membros/editar_membro.html", form=form, membro=membro)


# -----------------------------
# ❌ Exclusão de Membros
# -----------------------------
@member_bp.route("/excluir/<int:id>", methods=["POST"])
@login_required
@permission_required("membros", "delete")
def excluir_membro(id):
    membro = Member.query.get_or_404(id)
    nome_membro = membro.nome   # 👈 guarda o nome antes de excluir

    db.session.delete(membro)
    db.session.commit()
    flash(f"Membro {membro.nome} excluído com sucesso!", "danger")

    # Registrar log com nome do membro
    registrar_log(current_user.nome, f"Exclusão de Membro: {nome_membro}")

    return redirect(url_for("member.listar_membros"))


# -----------------------------
# 🎂 Aniversariantes do Mês
# -----------------------------
@member_bp.route("/aniversariantes", methods=["GET"])
@login_required
@permission_required("membros", "view")
def aniversariantes_mes():
    # Captura filtros
    mes = request.args.get("mes", type=int)
    funcao = request.args.get("funcao")
    dia_inicio = request.args.get("dia_inicio", type=int)
    dia_fim = request.args.get("dia_fim", type=int)
    page = request.args.get("page", 1, type=int)

    # Se não passar mês, usa o mês atual
    if not mes:
        mes = datetime.now().month

    # Query base (apenas membros ativos da congregação)
    query = (
        Member.query
        .filter(Member.data_nascimento.isnot(None))
        .filter(Member.data_saida.is_(None))
        .filter((Member.status.is_(None)) | (Member.status == "Ativo"))
        .filter(func.extract('month', Member.data_nascimento) == mes)
    )

    if funcao:
        query = query.filter(Member.funcao == funcao)
    if dia_inicio and dia_fim:
        query = query.filter(func.extract('day', Member.data_nascimento).between(dia_inicio, dia_fim))

    # 🔹 Paginação: ajuste o parâmetro `per_page` para definir quantos membros aparecem por página.
    # Exemplo: per_page=12 → só aparece paginação se houver mais de 12 membros.
    aniversariantes = query.order_by(func.extract('day', Member.data_nascimento)).paginate(page=page, per_page=12)

    meses = [
        "Janeiro","Fevereiro","Março","Abril","Maio","Junho",
        "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"
    ]

    funcoes = [f[0] for f in db.session.query(Member.funcao).distinct().all()]

    return render_template(
        "membros/aniversariantes_mes.html",
        aniversariantes=aniversariantes,
        meses=meses,
        mes_atual=meses[mes - 1],
        mes_selecionado=mes,
        funcoes=funcoes,
        funcao_selecionada=funcao,
        dia_inicio=dia_inicio,
        dia_fim=dia_fim,
        current_year=datetime.now().year
    )


# -----------------------------
# 🪪 Carteira de Membro (HTML)
# -----------------------------
@member_bp.route("/carteira/", methods=["GET"])
@member_bp.route("/carteira", methods=["GET"])
@member_bp.route("/carteira/<int:id>", methods=["GET"])
@member_bp.route("/carteira<int:id>", methods=["GET"])
@login_required   # 👈 protege a rota
@permission_required("membros", "view")
def carteira_membro(id=None):
    membro_id = id or request.args.get("id", type=int)

    if not membro_id:
        # Se nenhum ID for fornecido, seleciona o primeiro membro ativo
        primeiro_membro = Member.query.filter(Member.status == "Ativo").order_by(Member.id.asc()).first()
        if not primeiro_membro:
            primeiro_membro = Member.query.order_by(Member.id.asc()).first()
        if not primeiro_membro:
            flash("Nenhum membro cadastrado para emitir carteira.", "warning")
            return redirect(url_for("member.listar_membros"))
        membro = primeiro_membro
    else:
        membro = Member.query.get_or_404(membro_id)

    # Se o membro ainda não tiver número de carteirinha ou validade, gera e persiste automaticamente
    alterou = False
    if not membro.numero_carteira or not membro.numero_carteira.strip():
        membro.numero_carteira = gerar_proximo_numero_carteira()
        alterou = True

    if not membro.validade:
        dt_base = membro.data_cadastro or date.today()
        membro.validade = calcular_validade_carteira(dt_base)
        alterou = True

    if alterou:
        db.session.commit()

    todos_membros = Member.query.filter(Member.status == "Ativo").order_by(Member.nome.asc()).all()

    return render_template("membros/carteira_modelo.html", membro=membro, todos_membros=todos_membros)


def gerar_ou_renderizar_pdf(template_name, context, filename, fallback_template=None):
    """
    Gera o PDF usando WeasyPrint se disponível no ambiente.
    Caso contrário (ex: Windows sem bibliotecas nativas GTK/Pango ou erro de compilação),
    renderiza o HTML formatado com barra de ação para impressão nativa do navegador (window.print()).
    Garante ZERO erro 500, ZERO TypeError e ZERO falha para o usuário.
    """
    html_string = render_template(template_name, **context)
    if HTML is not None:
        try:
            pdf_bytes = HTML(string=html_string).write_pdf()
            response = make_response(pdf_bytes)
            response.headers['Content-Type'] = 'application/pdf'
            response.headers['Content-Disposition'] = f'inline; filename={filename}'
            return response
        except Exception as e:
            current_app.logger.warning(f"Falha ao compilar PDF via WeasyPrint ({e}). Utilizando renderização HTML para impressão.")

    # Modo fallback elegante: entrega o documento em HTML formatado com suporte a impressão
    return render_template(fallback_template or template_name, modo_impressao=True, **context)


# -----------------------------
# 📄 Carta de Recomendação (HTML + PDF)
# -----------------------------
@member_bp.route("/carta_recomendacao/<int:id>", methods=["GET"])
@member_bp.route("/carta_recomendacao/", methods=["GET"])
@member_bp.route("/carta_recomendacao", methods=["GET"])
@login_required   # 👈 protege a rota
@permission_required("membros", "view")
def carta_recomendacao(id=None):
    membro_id = id or request.args.get("id", type=int)
    if not membro_id:
        membro = Member.query.filter(Member.status == "Ativo").order_by(Member.id.asc()).first() or Member.query.first()
        if not membro:
            flash("Nenhum membro cadastrado para emitir carta de recomendação.", "warning")
            return redirect(url_for("member.listar_membros"))
    else:
        membro = Member.query.get_or_404(membro_id)

    todos_membros = Member.query.filter(Member.status == "Ativo").order_by(Member.nome.asc()).all()

    context = {
        "membro": membro,
        "todos_membros": todos_membros,
        "data_emissao": datetime.now().strftime("%d/%m/%Y")
    }
    return gerar_ou_renderizar_pdf(
        "membros/carta_recomendacao.html",
        context,
        filename=f"carta_recomendacao_{membro.id}.pdf"
    )


# -----------------------------
# 📄 Ficha de Membro (PDF)
# -----------------------------
@member_bp.route('/membro/<int:id>/ficha/pdf')
@login_required   # 👈 protege a rota
@permission_required("membros", "view")
def imprimir_ficha_pdf(id):
    membro = Member.query.get_or_404(id)

    foto_url = None
    if membro.foto:
        foto_url = url_for('static', filename=membro.foto, _external=True)

    context = {
        "membro": membro,
        "foto_url": foto_url,
        "current_date": date.today()
    }
    return gerar_ou_renderizar_pdf(
        'membros/ficha_pdf.html',
        context,
        filename=f"ficha_{membro.id}.pdf"
    )

# -----------------------------
# 📊 Relatório de Membros
# -----------------------------
@member_bp.route("/relatorio", methods=["GET"])
@login_required   # 👈 protege a rota
@permission_required("membros", "view")
def relatorio_membros():
    if not getattr(current_user, "is_admin", False):
        flash("Você não tem permissão para acessar o Relatório Estatístico.", "danger")
        return redirect(url_for("dashboard.dashboard"))

    sexo = request.args.get("sexo")
    status = request.args.get("status")
    estado_civil = request.args.get("estado_civil")
    funcao = request.args.get("funcao")

    query = Member.query
    if sexo:
        query = query.filter(Member.sexo == sexo)
    if status:
        query = query.filter(Member.status == status)
    if estado_civil:
        query = query.filter(Member.estado_civil == estado_civil)
    if funcao:
        query = query.filter(Member.funcao == funcao)

    membros = query.all()

    dist_sexo_raw = (
        query.with_entities(Member.sexo, func.count(Member.id))
        .group_by(Member.sexo)
        .all()
    )
    dist_status_raw = (
        query.with_entities(Member.status, func.count(Member.id))
        .group_by(Member.status)
        .all()
    )
    dist_estado_civil_raw = (
        query.with_entities(Member.estado_civil, func.count(Member.id))
        .group_by(Member.estado_civil)
        .all()
    )
    dist_funcao_raw = (
        query.with_entities(Member.funcao, func.count(Member.id))
        .group_by(Member.funcao)
        .all()
    )

    dist_sexo = [((s or "Não informado"), int(c)) for s, c in dist_sexo_raw]
    dist_status = [((st or "Não informado"), int(c)) for st, c in dist_status_raw]
    dist_estado_civil = [((ec or "Não informado"), int(c)) for ec, c in dist_estado_civil_raw]
    dist_funcao = [((f or "Não informado"), int(c)) for f, c in dist_funcao_raw]

    def calcula_idade(nasc):
        if not nasc:
            return None
        hoje = date.today()
        return hoje.year - nasc.year - ((hoje.month, hoje.day) < (nasc.month, nasc.day))

    faixas = []
    for m in membros:
        idade = calcula_idade(m.data_nascimento)
        if idade is None:
            continue
        if idade <= 18:
            faixas.append("0-18")
        elif idade <= 35:
            faixas.append("19-35")
        elif idade <= 60:
            faixas.append("36-60")
        else:
            faixas.append("60+")

    dist_idade = Counter(faixas)

    return render_template(
        "membros/relatorio_membros.html",
        membros=membros,
        dist_sexo=dist_sexo,
        dist_status=dist_status,
        dist_estado_civil=dist_estado_civil,
        dist_funcao=dist_funcao,
        dist_idade=dist_idade,
    )

# ----------------------------------------
# 📊 Relatório de Membros Estatísticos PDF
# -----------------------------------------
@member_bp.route("/relatorio/pdf")
@login_required   # 👈 protege a rota
@permission_required("membros", "view")
def relatorio_membros_pdf():
    if not getattr(current_user, "is_admin", False):
        flash("Você não tem permissão para acessar o Relatório Estatístico.", "danger")
        return redirect(url_for("dashboard.dashboard"))

    sexo = request.args.get("sexo")
    status = request.args.get("status")
    estado_civil = request.args.get("estado_civil")
    funcao = request.args.get("funcao")

    query = Member.query
    if sexo:
        query = query.filter(Member.sexo == sexo)
    if status:
        query = query.filter(Member.status == status)
    if estado_civil:
        query = query.filter(Member.estado_civil == estado_civil)
    if funcao:
        query = query.filter(Member.funcao == funcao)

    membros = query.all()

    context = {
        "membros": membros,
        "sexo": sexo,
        "status": status,
        "estado_civil": estado_civil,
        "funcao": funcao,
        "data_emissao": date.today().strftime("%d/%m/%Y")
    }
    return gerar_ou_renderizar_pdf(
        "membros/relatorio_membros_pdf.html",
        context,
        filename="relatorio_membros.pdf"
    )


# -----------------------------
# 🌐 Cadastro público de visitante
# -----------------------------
from sqlalchemy import or_, and_

@member_bp.route("/cadastro-visitante/<hash>", methods=["GET", "POST"])
def cadastro_visitante(hash):
    # ✅ valida se a hash existe e está ativa para tipo "visitante"
    link = PublicLink.query.filter_by(hash=hash, ativo=True, tipo="visitante").first_or_404()

    form = MemberForm()  # 👈 instancia o FlaskForm

    if request.method == "POST":
        nome = request.form.get("nome")
        telefone = request.form.get("telefone")
        email = request.form.get("email")
        data_nascimento_str = request.form.get("data_nascimento")
        sexo = request.form.get("sexo")
        estado_civil = request.form.get("estado_civil")
        conjuge = request.form.get("conjuge") if estado_civil == "Casado" else None
        endereco = request.form.get("endereco")
        bairro = request.form.get("bairro")
        naturalidade = request.form.get("naturalidade")
        cep = request.form.get("cep")
        observacoes = request.form.get("observacoes")

        # 🔒 Converte data de nascimento para objeto date
        data_nascimento = None
        if data_nascimento_str:
            try:
                data_nascimento = datetime.strptime(data_nascimento_str, "%Y-%m-%d").date()
            except ValueError:
                data_nascimento = None

        # 🚫 Verifica duplicidade (mesmo nome+telefone OU mesmo email)
        conditions = [
            and_(Member.nome == nome, Member.telefone == telefone)
        ]
        if email:
            conditions.append(Member.email == email)

        existente = Member.query.filter(or_(*conditions)).first()

        if existente:
            # 👉 se já existe, apenas volta para o formulário sem cadastrar de novo
            return render_template("membros/cadastro_visitante.html", form=form, hash=hash)

        # ✅ Se não existe, cria novo visitante
        visitante = Member(
            nome=nome,
            telefone=telefone,
            email=email,
            data_nascimento=data_nascimento,
            sexo=sexo,
            estado_civil=estado_civil,
            conjuge=conjuge,
            endereco=endereco,
            bairro=bairro,
            naturalidade=naturalidade,
            cep=cep,
            observacoes=sanitizar_html(observacoes),
            funcao="Visitante",
            status="Ativo",
            data_cadastro=datetime.utcnow()
        )
        db.session.add(visitante)
        db.session.commit()

        # ➕ Registrar log
        registrar_log(nome, f"Cadastro público de visitante: {nome}")

        # 👉 após cadastrar, renderiza a tela de sucesso
        return render_template("membros/success.html", visitante=visitante, hash=hash)

    # ✅ se GET, renderiza o formulário estilizado
    return render_template("membros/cadastro_visitante.html", form=form, hash=hash)

    
# -----------------------------
# 📄 Relatório em PDF de Aniversariantes
# -----------------------------
@member_bp.route("/aniversariantes/pdf", methods=["GET"])
@member_bp.route("/membros/aniversariantes/pdf", methods=["GET"])
@login_required
@permission_required("membros", "view")
def exportar_aniversariantes_pdf():
    # 🔹 Captura filtros da URL
    mes = request.args.get("mes", type=int)
    funcao = request.args.get("funcao")
    dia_inicio = request.args.get("dia_inicio", type=int)
    dia_fim = request.args.get("dia_fim", type=int)

    # 🔹 Se não for passado mês, usa o mês atual
    if not mes:
        mes = datetime.now().month

    # 🔹 Filtros diretos (apenas membros ativos da congregação)
    query = (
        Member.query
        .filter(Member.data_nascimento.isnot(None))
        .filter(Member.data_saida.is_(None))
        .filter((Member.status.is_(None)) | (Member.status == "Ativo"))
        .filter(func.extract('month', Member.data_nascimento) == mes)
    )

    if funcao:
        query = query.filter(Member.funcao == funcao)
    if dia_inicio and dia_fim:
        query = query.filter(
            func.extract('day', Member.data_nascimento).between(dia_inicio, dia_fim)
        )

    aniversariantes = query.order_by(Member.data_nascimento).all()

    # 🔹 Data de emissão (somente dia/mês/ano)
    data_emissao = datetime.now().strftime("%d/%m/%Y")

    context = {
        "aniversariantes": aniversariantes,
        "current_year": datetime.now().year,
        "data_emissao": data_emissao
    }
    return gerar_ou_renderizar_pdf(
        "membros/aniversariantes_pdf.html",
        context,
        filename="aniversariantes.pdf"
    )


# ------------------------------------------------------------------------------
# 👤 Transformar Membro em Usuário do Sistema (Sem duplicação de cadastro)
# ------------------------------------------------------------------------------
@member_bp.route("/<int:id>/tornar-usuario", methods=["POST"])
@login_required
def tornar_usuario(id):
    if not (current_user.is_admin or current_user.has_permission("usuarios", "create") or current_user.has_permission("membros", "edit")):
        flash("Você não tem permissão para criar usuários.", "danger")
        return redirect(url_for("member.listar_membros"))

    membro = Member.query.get_or_404(id)
    if membro.user:
        flash(f"O membro '{membro.nome}' já possui uma conta de usuário vinculada ({membro.user.email}).", "warning")
        return redirect(url_for("member.listar_membros"))

    email = request.form.get("email", "").strip().lower()
    senha = request.form.get("senha", "").strip()
    confirmar_senha = request.form.get("confirmar_senha", "").strip()
    perfil = request.form.get("perfil", "professor_ebd").strip()

    if not email or "@" not in email:
        flash("Informe um e-mail válido para o login do usuário.", "danger")
        return redirect(url_for("member.listar_membros"))

    existente = User.query.filter_by(email=email).first()
    if existente:
        flash(f"Este e-mail '{email}' já está em uso por outro usuário do sistema.", "danger")
        return redirect(url_for("member.listar_membros"))

    if len(senha) < 6:
        flash("A senha deve conter no mínimo 6 caracteres.", "danger")
        return redirect(url_for("member.listar_membros"))

    if senha != confirmar_senha:
        flash("A confirmação de senha não confere.", "danger")
        return redirect(url_for("member.listar_membros"))

    is_admin = (perfil == "admin")
    usuario = User(
        nome=membro.nome,
        email=email,
        ativo=True,
        is_admin=is_admin,
        foto=membro.foto,
        member_id=membro.id
    )
    usuario.set_password(senha)
    db.session.add(usuario)
    db.session.flush()

    # Perfis predefinidos de permissões
    perfis_permissoes = {
        "professor_ebd": [("ebd", "view"), ("ebd", "frequencia"), ("perfil", "view"), ("perfil", "password")],
        "coordenador_ebd": [("ebd", "view"), ("ebd", "create"), ("ebd", "edit"), ("ebd", "delete"), ("ebd", "frequencia"), ("perfil", "view"), ("perfil", "password")],
        "secretario": [("membros", "view"), ("membros", "create"), ("membros", "edit"), ("atas", "view"), ("atas", "create"), ("cartas", "view"), ("cartas", "create"), ("certificados", "view"), ("certificados", "create"), ("ebd", "view"), ("perfil", "view"), ("perfil", "password")],
        "financeiro": [("financeiro", "view"), ("financeiro", "create"), ("financeiro", "edit"), ("perfil", "view"), ("perfil", "password")],
        "comum": [("perfil", "view"), ("perfil", "password")]
    }

    if not is_admin:
        perms_a_adicionar = perfis_permissoes.get(perfil, perfis_permissoes["professor_ebd"])
        for area, acao in perms_a_adicionar:
            perm = Permission.query.filter_by(area=area, action=acao).first()
            if not perm:
                perm = Permission(area=area, action=acao)
                db.session.add(perm)
                db.session.flush()
            db.session.add(UserPermission(user_id=usuario.id, permission_id=perm.id))

    db.session.commit()
    user_ident = getattr(current_user, "nome", None) or getattr(current_user, "email", "Admin")
    registrar_log(user_ident, f"Transformou membro '{membro.nome}' em usuário ({email}) com perfil: {perfil}")
    flash(f"Conta de acesso criada com sucesso para '{membro.nome}' ({email})!", "success")
    return redirect(url_for("member.listar_membros"))


@member_bp.route("/<int:id>/toggle-usuario", methods=["POST"])
@login_required
def toggle_usuario_membro(id):
    if not (current_user.is_admin or current_user.has_permission("usuarios", "edit")):
        flash("Você não tem permissão para alterar status de usuários.", "danger")
        return redirect(url_for("member.listar_membros"))

    membro = Member.query.get_or_404(id)
    if not membro.user:
        flash("Este membro não possui conta de usuário vinculada.", "warning")
        return redirect(url_for("member.listar_membros"))

    membro.user.ativo = not membro.user.ativo
    db.session.commit()
    user_ident = getattr(current_user, "nome", None) or getattr(current_user, "email", "Admin")
    status_str = "ativado" if membro.user.ativo else "desativado"
    registrar_log(user_ident, f"Alterou status do usuário vinculado a '{membro.nome}' para {status_str}")
    flash(f"Acesso ao sistema do membro '{membro.nome}' foi {status_str} com sucesso!", "success" if membro.user.ativo else "warning")
    return redirect(url_for("member.listar_membros"))


