from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify
from app.extensions import db
from app.models import Patrimonio
from app.routes.patrimonio.forms import PatrimonioForm
from datetime import datetime
import re
import unicodedata
from werkzeug.datastructures import MultiDict
from flask_login import login_required, current_user
from utils.logs import registrar_log
from utils.sanitizer import sanitizar_html
from app.decorators import permission_required

patrimonio_bp = Blueprint("patrimonio", __name__, url_prefix="/patrimonios")


def obter_prefixo_categoria(categoria: str) -> str:
    """Retorna o prefixo oficial padronizado de etiqueta de tombamento para uma categoria."""
    if not categoria:
        return "PAT-GER-"
    
    cat_clean = categoria.strip().lower()
    mapeamento = {
        "imóveis": "PAT-IMO-",
        "imoveis": "PAT-IMO-",
        "imóvel": "PAT-IMO-",
        "veículos": "PAT-VEI-",
        "veiculos": "PAT-VEI-",
        "veículo": "PAT-VEI-",
        "equipamentos": "PAT-EQU-",
        "equipamento": "PAT-EQU-",
        "móveis": "PAT-MOV-",
        "moveis": "PAT-MOV-",
        "móvel": "PAT-MOV-",
    }
    if cat_clean in mapeamento:
        return mapeamento[cat_clean]

    # Fallback dinâmico: 3 letras da categoria sem acentos
    nfkd = unicodedata.normalize("NFKD", categoria)
    sem_acento = "".join([c for c in nfkd if not unicodedata.combining(c)])
    letras = "".join([c for c in sem_acento if c.isalnum()]).upper()
    cod = letras[:3] if len(letras) >= 3 else (letras + "XXX")[:3]
    return f"PAT-{cod}-"


def gerar_proxima_etiqueta_patrimonio(categoria: str) -> str:
    """Calcula a próxima etiqueta sequencial para a categoria especificada mantendo o padrão."""
    prefixo = obter_prefixo_categoria(categoria)
    itens = Patrimonio.query.filter(Patrimonio.numero.like(f"{prefixo}%")).all()
    maior_idx = 0
    for item in itens:
        if not item.numero:
            continue
        match = re.search(rf"^{re.escape(prefixo)}(\d+)$", item.numero.strip())
        if match:
            try:
                num = int(match.group(1))
                if num > maior_idx:
                    maior_idx = num
            except ValueError:
                pass

    proximo = maior_idx + 1
    while Patrimonio.query.filter_by(numero=f"{prefixo}{proximo:03d}").first() is not None:
        proximo += 1

    return f"{prefixo}{proximo:03d}"


# -----------------------------
# 🏷️ API: Próxima Etiqueta de Tombamento
# -----------------------------
@patrimonio_bp.route("/api/proxima-etiqueta", methods=["GET"])
@login_required
@permission_required("patrimonios", "view")
def api_proxima_etiqueta():
    categoria = request.args.get("categoria", "").strip()
    etiqueta = gerar_proxima_etiqueta_patrimonio(categoria)
    return jsonify({"sucesso": True, "categoria": categoria, "etiqueta": etiqueta})


def _normalize_date_for_form(formdata: MultiDict, field_name: str = "data_entrada"):
    """Converte yyyy-mm-dd (do input type='date') para dd-mm-aaaa esperado pelo DateField."""
    if field_name in formdata and formdata[field_name]:
        raw = formdata[field_name]
        try:
            iso = datetime.strptime(raw, "%Y-%m-%d").strftime("%d-%m-%Y")
            formdata[field_name] = iso
        except ValueError:
            try:
                datetime.strptime(raw, "%d-%m-%Y")
            except ValueError:
                pass

def _to_float(value):
    """Converte Decimal do WTForms para float do SQLAlchemy (Float)."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

# -----------------------------
# 📋 Listar Patrimônios com paginação
# -----------------------------
@patrimonio_bp.route("/", methods=["GET"])
@login_required
@permission_required("patrimonios", "view")
def listar_patrimonios():
    page = request.args.get("page", 1, type=int)
    patrimonios = Patrimonio.query.order_by(Patrimonio.nome.asc()).paginate(page=page, per_page=10)
    return render_template("patrimonios/listar_patrimonios.html", patrimonios=patrimonios)


# -----------------------------
# ➕ Criar novo Patrimônio
# -----------------------------
@patrimonio_bp.route("/novo", methods=["GET", "POST"])
@login_required
@permission_required("patrimonios", "create")
def novo_patrimonio():
    if request.method == "POST":
        formdata = MultiDict(request.form)
        _normalize_date_for_form(formdata)
        form = PatrimonioForm(formdata=formdata)
    else:
        form = PatrimonioForm()
        # Pré-preenche com a próxima etiqueta sequencial da categoria padrão
        cat_inicial = form.categoria.data or "Equipamentos"
        form.numero.data = gerar_proxima_etiqueta_patrimonio(cat_inicial)

    if form.validate_on_submit():
        etiqueta_final = (form.numero.data or "").strip()
        if not etiqueta_final:
            etiqueta_final = gerar_proxima_etiqueta_patrimonio(form.categoria.data)

        item = Patrimonio(
            nome=form.nome.data,
            descricao=sanitizar_html(form.descricao.data),
            categoria=form.categoria.data,
            numero=etiqueta_final,
            valor=_to_float(form.valor.data),
            data_entrada=form.data_entrada.data,
            situacao=form.situacao.data
        )
        db.session.add(item)
        db.session.commit()
        registrar_log(current_user.nome, f"Cadastrou patrimônio: {item.nome} ({item.numero})", "sucesso")
        flash(f"Patrimônio {item.nome} cadastrado com sucesso! Etiqueta: {item.numero}", "success")
        return redirect(url_for("patrimonio.listar_patrimonios"))
    else:
        if request.method == "POST":
            current_app.logger.debug(f"Erros de validação ao criar patrimônio: {form.errors}")
    return render_template("patrimonios/novo_patrimonio.html", form=form)

# -----------------------------
# ✏️ Editar Patrimônio
# -----------------------------
@patrimonio_bp.route("/editar/<int:id>", methods=["GET", "POST"])
@login_required
@permission_required("patrimonios", "edit")
def editar_patrimonio(id):
    item = Patrimonio.query.get_or_404(id)

    if request.method == "POST":
        formdata = MultiDict(request.form)
        _normalize_date_for_form(formdata)
        form = PatrimonioForm(formdata=formdata, obj=item)
    else:
        form = PatrimonioForm(obj=item)

    if form.validate_on_submit():
        item.nome = form.nome.data
        item.descricao = sanitizar_html(form.descricao.data)
        item.categoria = form.categoria.data
        item.numero = form.numero.data
        item.valor = _to_float(form.valor.data)
        item.data_entrada = form.data_entrada.data
        item.situacao = form.situacao.data

        db.session.commit()
        registrar_log(current_user.nome, f"Editou patrimônio: {item.nome}", "sucesso")
        flash(f"Patrimônio {item.nome} atualizado com sucesso!", "success")
        return redirect(url_for("patrimonio.listar_patrimonios"))
    else:
        if request.method == "POST":
            current_app.logger.debug(f"Erros de validação ao editar patrimônio: {form.errors}")
    return render_template("patrimonios/editar_patrimonio.html", form=form, item=item)


# -----------------------------
# ❌ Excluir Patrimônio
# -----------------------------
@patrimonio_bp.route("/excluir/<int:id>", methods=["POST"])
@login_required
@permission_required("patrimonios", "delete")
def excluir_patrimonio(id):
    item = Patrimonio.query.get_or_404(id)
    db.session.delete(item)
    db.session.commit()
    registrar_log(current_user.nome, f"Excluiu patrimônio: {item.nome}", "sucesso")
    flash(f"Patrimônio {item.nome} excluído com sucesso!", "danger")
    return redirect(url_for("patrimonio.listar_patrimonios"))


# -----------------------------
# 🔍 Buscar Patrimônios com paginação
# -----------------------------
@patrimonio_bp.route("/buscar", methods=["GET"])
@login_required
@permission_required("patrimonios", "view")
def buscar_patrimonios():
    termo = request.args.get("q", "").strip().lower()
    page = request.args.get("page", 1, type=int)

    query = Patrimonio.query
    if termo:
        query = query.filter(
            (Patrimonio.nome.ilike(f"%{termo}%")) |
            (Patrimonio.categoria.ilike(f"%{termo}%")) |
            (Patrimonio.numero.ilike(f"%{termo}%"))
        )

    query = query.order_by(Patrimonio.nome.asc())
    patrimonios = query.paginate(page=page, per_page=10)

    if termo:
        if patrimonios.total == 0:
            flash("Nenhum patrimônio corresponde ao termo pesquisado", "warning")
        elif patrimonios.total == 1:
            flash("1 patrimônio encontrado", "info")
        else:
            flash(f"{patrimonios.total} patrimônio(s) encontrados", "info")

        registrar_log(current_user.nome, f"Buscou patrimônio com termo: {termo}", "sucesso")

    return render_template("patrimonios/listar_patrimonios.html", patrimonios=patrimonios, termo=termo)
    

# -----------------------------
# 📦 Inventário de Patrimônios
# -----------------------------
@patrimonio_bp.route("/inventario", methods=["GET"])
@login_required
@permission_required("patrimonios", "view")
def inventario():
    categoria = request.args.get("categoria", "").strip()
    situacao = request.args.get("situacao", "").strip()

    query = Patrimonio.query

    if categoria:
        query = query.filter(Patrimonio.categoria.ilike(f"%{categoria}%"))
    if situacao:
        query = query.filter(Patrimonio.situacao == situacao)

    patrimonios = query.order_by(Patrimonio.data_entrada.asc()).all()

    categorias = {}
    total = 0
    for item in patrimonios:
        valor = item.valor or 0
        total += valor
        cat = item.categoria or "Sem categoria"
        if cat in categorias:
            categorias[cat]["qtde"] += 1
            categorias[cat]["valor"] += valor
        else:
            categorias[cat] = {"qtde": 1, "valor": valor}

    if not patrimonios and (categoria or situacao):
        flash("Nenhum patrimônio encontrado com os filtros aplicados", "warning")

    registrar_log(current_user.nome, "Gerou inventário de patrimônios", "sucesso")

    return render_template(
        "patrimonios/inventario.html",
        patrimonios=patrimonios,
        categorias=categorias,
        total=total,
        categoria=categoria,
        situacao=situacao
    )

