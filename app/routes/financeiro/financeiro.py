from flask import Blueprint, render_template, redirect, url_for, flash, request, Response, current_app
from datetime import datetime, date
from collections import defaultdict
import csv, io, os
from sqlalchemy import or_, func, extract

from app.extensions import db
from app.models import Financeiro, Member, Igreja
from app.models.financeiro import (
    CATEGORIAS_RECEITAS_PADRAO,
    CATEGORIAS_DESPESAS_PADRAO,
    DEPARTAMENTOS_PADRAO,
    CONTAS_PADRAO,
    FORMAS_PAGAMENTO_PADRAO
)
from app.routes.financeiro.forms import (
    EntradaForm, SaidaForm, FiltroRelatorioForm, ComprovanteForm
)
from app.services.upload_service import UploadService
from flask_login import login_required, current_user
from utils.logs import registrar_log
from utils.sanitizer import sanitizar_html
from app.decorators import permission_required

financeiro_bp = Blueprint("financeiro", __name__, url_prefix="/financeiro")


def _get_membro_choices():
    """Retorna lista de tuplas (id, nome) para SelectField de membros."""
    membros = Member.query.order_by(Member.nome.asc()).all()
    return [(0, "-- Selecione um Membro (Opcional) --")] + [(m.id, f"{m.nome} (CPF: {m.cpf or 'N/I'})") for m in membros]


def _parse_filter_date(s):
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            continue
    return None


# -----------------------------
# 📊 Painel Geral Financeiro
# -----------------------------
@financeiro_bp.route('/')
@login_required
@permission_required("financeiro", "view")
def financeiro():
    hoje = date.today()
    mes_atual = hoje.month
    ano_atual = hoje.year

    # 1. Totais do mês corrente
    entradas_mes = db.session.query(func.coalesce(func.sum(Financeiro.valor), 0.0)).filter(
        Financeiro.tipo == "Entrada",
        extract("month", Financeiro.data) == mes_atual,
        extract("year", Financeiro.data) == ano_atual
    ).scalar()

    saidas_mes = db.session.query(func.coalesce(func.sum(Financeiro.valor), 0.0)).filter(
        Financeiro.tipo == "Saída",
        extract("month", Financeiro.data) == mes_atual,
        extract("year", Financeiro.data) == ano_atual
    ).scalar()

    saldo_mes = float(entradas_mes) - float(saidas_mes)

    # 2. Total acumulado geral de todas as épocas
    total_entradas_geral = db.session.query(func.coalesce(func.sum(Financeiro.valor), 0.0)).filter(Financeiro.tipo == "Entrada").scalar()
    total_saidas_geral = db.session.query(func.coalesce(func.sum(Financeiro.valor), 0.0)).filter(Financeiro.tipo == "Saída").scalar()
    saldo_geral = float(total_entradas_geral) - float(total_saidas_geral)

    # 3. Saldo por Conta / Fundo Eclesiástico
    saldos_contas = []
    for c in CONTAS_PADRAO:
        ent = db.session.query(func.coalesce(func.sum(Financeiro.valor), 0.0)).filter(
            Financeiro.tipo == "Entrada", Financeiro.conta == c
        ).scalar()
        sai = db.session.query(func.coalesce(func.sum(Financeiro.valor), 0.0)).filter(
            Financeiro.tipo == "Saída", Financeiro.conta == c
        ).scalar()
        total_conta = float(ent) - float(sai)
        if total_conta != 0 or ent > 0 or sai > 0:
            saldos_contas.append({
                "conta": c,
                "entradas": float(ent),
                "saidas": float(sai),
                "saldo": total_conta
            })

    # 4. Histórico dos últimos 6 meses para gráfico
    def month_key(d: date):
        return d.strftime("%m/%Y")

    todos = Financeiro.query.order_by(Financeiro.data.asc()).all()
    meses_unicos = sorted(list({month_key(r.data) for r in todos}), key=lambda x: datetime.strptime("01/"+x, "%d/%m/%Y"))[-6:]
    if not meses_unicos:
        meses_unicos = [hoje.strftime("%m/%Y")]

    por_mes = {m: {"Entradas": 0.0, "Saídas": 0.0} for m in meses_unicos}
    for r in todos:
        mk = month_key(r.data)
        if mk in por_mes:
            if r.tipo == "Entrada":
                por_mes[mk]["Entradas"] += float(r.valor)
            elif r.tipo == "Saída":
                por_mes[mk]["Saídas"] += float(r.valor)

    labels = meses_unicos
    entradas_data = [por_mes[m]["Entradas"] for m in labels]
    saidas_data = [por_mes[m]["Saídas"] for m in labels]

    # 5. Últimos 5 lançamentos gerais
    ultimos_lancamentos = Financeiro.query.order_by(Financeiro.data.desc(), Financeiro.id.desc()).limit(5).all()

    return render_template(
        'financeiro/financeiro.html',
        total_entradas_mes=float(entradas_mes),
        total_saidas_mes=float(saidas_mes),
        saldo_mes=saldo_mes,
        saldo_geral=saldo_geral,
        saldos_contas=saldos_contas,
        labels=labels,
        entradas_data=entradas_data,
        saidas_data=saidas_data,
        ultimos_lancamentos=ultimos_lancamentos
    )


# -----------------------------
# 📥 Gestão de Entradas (Receitas Eclesiásticas)
# -----------------------------
@financeiro_bp.route('/entradas', methods=['GET', 'POST'])
@login_required
@permission_required("financeiro", "view")
def entradas():
    form = EntradaForm()
    form.membro_id.choices = _get_membro_choices()

    if form.validate_on_submit():
        if not current_user.has_permission("financeiro", "create"):
            flash("Você não tem permissão para cadastrar entradas.", "danger")
            registrar_log(current_user.nome, "Tentou cadastrar entrada sem permissão", "falha")
            return redirect(url_for("financeiro.entradas"))

        # Upload seguro de comprovante
        comprovante_rel_path = None
        if form.comprovante.data:
            comprovante_rel_path = UploadService.save_image(form.comprovante.data, subfolder="financeiro")

        membro_selecionado = form.membro_id.data if form.membro_id.data and form.membro_id.data > 0 else None
        cpf_membro_val = None
        if membro_selecionado:
            m = db.session.get(Member, membro_selecionado)
            if m and m.cpf:
                cpf_membro_val = m.cpf

        nova = Financeiro(
            tipo="Entrada",
            categoria=form.tipo_receita.data,
            membro_id=membro_selecionado,
            cpf_membro=cpf_membro_val,
            valor=float(form.valor.data),
            data=form.data.data,
            forma_pagamento=form.forma_pagamento.data,
            conta=form.conta.data,
            departamento=form.departamento.data,
            descricao=form.descricao.data.strip() if form.descricao.data else form.tipo_receita.data,
            observacoes=sanitizar_html(form.observacoes.data) if form.observacoes.data else None,
            usuario=current_user.nome,
            comprovante=comprovante_rel_path
        )
        db.session.add(nova)
        db.session.commit()
        registrar_log(current_user.nome, f"Registrou entrada {nova.categoria} - R$ {nova.valor:.2f}", "sucesso")
        flash(f"Entrada de R$ {nova.valor:.2f} registrada com sucesso!", "success")
        return redirect(url_for('financeiro.entradas'))

    # Filtros de busca
    filtro = request.args.get("filtro", "").strip()
    filtro_categoria = request.args.get("categoria", "").strip()
    filtro_data_inicio = request.args.get("inicio", "").strip()
    filtro_data_fim = request.args.get("fim", "").strip()

    query = Financeiro.query.outerjoin(Member).filter(Financeiro.tipo == "Entrada")
    if filtro:
        query = query.filter(
            or_(
                Financeiro.descricao.ilike(f"%{filtro}%"),
                Financeiro.conta.ilike(f"%{filtro}%"),
                Financeiro.forma_pagamento.ilike(f"%{filtro}%"),
                Member.nome.ilike(f"%{filtro}%"),
            )
        )
    if filtro_categoria:
        query = query.filter(Financeiro.categoria == filtro_categoria)

    dt_ini = _parse_filter_date(filtro_data_inicio)
    dt_fim = _parse_filter_date(filtro_data_fim)
    if dt_ini:
        query = query.filter(Financeiro.data >= dt_ini)
    if dt_fim:
        query = query.filter(Financeiro.data <= dt_fim)

    page = request.args.get("page", 1, type=int)
    registros = query.order_by(Financeiro.data.desc(), Financeiro.id.desc()).paginate(page=page, per_page=12, error_out=False)

    # Totais do mês
    hoje = date.today()
    total_mes = db.session.query(func.coalesce(func.sum(Financeiro.valor), 0.0)).filter(
        Financeiro.tipo == "Entrada",
        extract("month", Financeiro.data) == hoje.month,
        extract("year", Financeiro.data) == hoje.year
    ).scalar()

    total_filtrado = sum(r.valor for r in query.all())

    return render_template(
        "financeiro/entradas.html",
        form=form,
        entradas=registros.items,
        pagination=registros,
        total_mes=float(total_mes),
        total_filtrado=float(total_filtrado),
        categorias_receitas=CATEGORIAS_RECEITAS_PADRAO,
        filtro=filtro,
        filtro_categoria=filtro_categoria,
        filtro_data_inicio=filtro_data_inicio,
        filtro_data_fim=filtro_data_fim
    )


# -----------------------------
# 📤 Gestão de Saídas (Despesas Eclesiásticas)
# -----------------------------
@financeiro_bp.route('/saidas', methods=['GET', 'POST'])
@login_required
@permission_required("financeiro", "view")
def saidas():
    form = SaidaForm()

    if form.validate_on_submit():
        if not current_user.has_permission("financeiro", "create"):
            flash("Você não tem permissão para registrar saídas.", "danger")
            registrar_log(current_user.nome, "Tentou registrar saída sem permissão", "falha")
            return redirect(url_for("financeiro.saidas"))

        comprovante_rel_path = None
        if form.comprovante.data:
            comprovante_rel_path = UploadService.save_image(form.comprovante.data, subfolder="financeiro")

        nova = Financeiro(
            tipo="Saída",
            categoria=form.categoria.data,
            departamento=form.departamento.data,
            valor=float(form.valor.data),
            data=form.data.data,
            forma_pagamento=form.forma_pagamento.data,
            conta=form.conta.data,
            cnpj_fornecedor=form.cnpj_fornecedor.data.strip() if form.cnpj_fornecedor.data else None,
            descricao=form.descricao.data.strip() if form.descricao.data else form.categoria.data,
            observacoes=sanitizar_html(form.observacoes.data) if form.observacoes.data else None,
            usuario=current_user.nome,
            comprovante=comprovante_rel_path
        )
        db.session.add(nova)
        db.session.commit()
        registrar_log(current_user.nome, f"Registrou saída {nova.categoria} - R$ {nova.valor:.2f}", "sucesso")
        flash(f"Despesa de R$ {nova.valor:.2f} registrada com sucesso!", "success")
        return redirect(url_for('financeiro.saidas'))

    filtro = request.args.get("filtro", "").strip()
    filtro_departamento = request.args.get("departamento", "").strip()
    filtro_data_inicio = request.args.get("inicio", "").strip()
    filtro_data_fim = request.args.get("fim", "").strip()

    query = Financeiro.query.filter_by(tipo="Saída")
    if filtro:
        query = query.filter(
            or_(
                Financeiro.descricao.ilike(f"%{filtro}%"),
                Financeiro.categoria.ilike(f"%{filtro}%"),
                Financeiro.cnpj_fornecedor.ilike(f"%{filtro}%")
            )
        )
    if filtro_departamento:
        query = query.filter(Financeiro.departamento == filtro_departamento)

    dt_ini = _parse_filter_date(filtro_data_inicio)
    dt_fim = _parse_filter_date(filtro_data_fim)
    if dt_ini:
        query = query.filter(Financeiro.data >= dt_ini)
    if dt_fim:
        query = query.filter(Financeiro.data <= dt_fim)

    page = request.args.get("page", 1, type=int)
    registros = query.order_by(Financeiro.data.desc(), Financeiro.id.desc()).paginate(page=page, per_page=12, error_out=False)

    hoje = date.today()
    total_mes = db.session.query(func.coalesce(func.sum(Financeiro.valor), 0.0)).filter(
        Financeiro.tipo == "Saída",
        extract("month", Financeiro.data) == hoje.month,
        extract("year", Financeiro.data) == hoje.year
    ).scalar()

    total_filtrado = sum(r.valor for r in query.all())

    return render_template(
        "financeiro/saidas.html",
        form=form,
        saidas=registros.items,
        pagination=registros,
        total_mes=float(total_mes),
        total_filtrado=float(total_filtrado),
        departamentos=DEPARTAMENTOS_PADRAO,
        filtro=filtro,
        filtro_departamento=filtro_departamento,
        filtro_data_inicio=filtro_data_inicio,
        filtro_data_fim=filtro_data_fim
    )


# -----------------------------
# 🤝 Gestão Exclusiva de Dízimos & Contribuições Eclesiásticas
# -----------------------------
@financeiro_bp.route('/dizimos')
@login_required
@permission_required("financeiro", "view")
def dizimos():
    hoje = date.today()
    ano = request.args.get("ano", hoje.year, type=int)
    mes = request.args.get("mes", hoje.month, type=int)
    membro_id = request.args.get("membro_id", type=int)

    query = Financeiro.query.filter(
        Financeiro.tipo == "Entrada",
        Financeiro.categoria.ilike("%Dízimo%")
    )

    if ano:
        query = query.filter(extract("year", Financeiro.data) == ano)
    if mes and mes > 0:
        query = query.filter(extract("month", Financeiro.data) == mes)
    if membro_id and membro_id > 0:
        query = query.filter(Financeiro.membro_id == membro_id)

    page = request.args.get("page", 1, type=int)
    dizimos_paginados = query.order_by(Financeiro.data.desc()).paginate(page=page, per_page=15, error_out=False)

    # Indicadores
    total_dizimos_periodo = sum(d.valor for d in query.all())
    dizimistas_distintos = len({d.membro_id for d in query.all() if d.membro_id})
    membros = Member.query.order_by(Member.nome.asc()).all()

    return render_template(
        "financeiro/dizimos.html",
        dizimos=dizimos_paginados.items,
        pagination=dizimos_paginados,
        total_periodo=total_dizimos_periodo,
        dizimistas_distintos=dizimistas_distintos,
        membros=membros,
        ano_selecionado=ano,
        mes_selecionado=mes,
        membro_selecionado_id=membro_id
    )


# -----------------------------
# 📜 Extrato Anual de Dízimos e Ofertas do Membro (para IRPF / Prestação)
# -----------------------------
@financeiro_bp.route('/dizimos/extrato/<int:membro_id>')
@login_required
@permission_required("financeiro", "view")
def extrato_dizimos_membro(membro_id):
    membro = db.session.get(Member, membro_id)
    if not membro:
        flash("Membro não encontrado.", "danger")
        return redirect(url_for("financeiro.dizimos"))

    ano = request.args.get("ano", date.today().year, type=int)
    igreja = Igreja.query.first()

    lancamentos = Financeiro.query.filter(
        Financeiro.membro_id == membro.id,
        Financeiro.tipo == "Entrada",
        extract("year", Financeiro.data) == ano
    ).order_by(Financeiro.data.asc()).all()

    # Agrupar por mês
    meses_pt = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    resumo_mensal = [{"mes_num": i+1, "mes_nome": meses_pt[i], "total": 0.0, "itens": []} for i in range(12)]

    total_anual = 0.0
    for l in lancamentos:
        m_idx = l.data.month - 1
        resumo_mensal[m_idx]["total"] += l.valor
        resumo_mensal[m_idx]["itens"].append(l)
        total_anual += l.valor

    return render_template(
        "financeiro/extrato_membro.html",
        membro=membro,
        ano=ano,
        igreja=igreja,
        lancamentos=lancamentos,
        resumo_mensal=resumo_mensal,
        total_anual=total_anual,
        data_emissao=datetime.now()
    )


# -----------------------------
# 🏛️ Balancete Mensal Oficial da Igreja (Prestação de Contas / Assembleia)
# -----------------------------
@financeiro_bp.route('/balancete')
@login_required
@permission_required("financeiro", "view")
def balancete_mensal():
    hoje = date.today()
    mes = request.args.get("mes", hoje.month, type=int)
    ano = request.args.get("ano", hoje.year, type=int)

    igreja = Igreja.query.first()
    meses_pt = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    nome_mes = meses_pt[mes - 1]

    # 1. Entradas do mês agrupadas por Categoria
    entradas_query = Financeiro.query.filter(
        Financeiro.tipo == "Entrada",
        extract("month", Financeiro.data) == mes,
        extract("year", Financeiro.data) == ano
    ).all()

    entradas_por_categoria = defaultdict(float)
    total_entradas = 0.0
    for e in entradas_query:
        entradas_por_categoria[e.categoria] += e.valor
        total_entradas += e.valor

    # 2. Saídas do mês agrupadas por Departamento e Categoria
    saidas_query = Financeiro.query.filter(
        Financeiro.tipo == "Saída",
        extract("month", Financeiro.data) == mes,
        extract("year", Financeiro.data) == ano
    ).all()

    saidas_por_depto = defaultdict(float)
    saidas_por_categoria = defaultdict(float)
    total_saidas = 0.0
    for s in saidas_query:
        saidas_por_depto[s.departamento] += s.valor
        saidas_por_categoria[s.categoria] += s.valor
        total_saidas += s.valor

    # 3. Saldo por Conta / Fundo
    primeiro_dia_mes = date(ano, mes, 1)
    saldos_fundos = []
    for conta in CONTAS_PADRAO:
        # Saldo anterior (acumulado antes deste mês)
        ent_ant = db.session.query(func.coalesce(func.sum(Financeiro.valor), 0.0)).filter(
            Financeiro.tipo == "Entrada", Financeiro.conta == conta, Financeiro.data < primeiro_dia_mes
        ).scalar()
        sai_ant = db.session.query(func.coalesce(func.sum(Financeiro.valor), 0.0)).filter(
            Financeiro.tipo == "Saída", Financeiro.conta == conta, Financeiro.data < primeiro_dia_mes
        ).scalar()
        saldo_ant = float(ent_ant) - float(sai_ant)

        # Movimento do mês
        ent_mes = sum(e.valor for e in entradas_query if e.conta == conta)
        sai_mes = sum(s.valor for s in saidas_query if s.conta == conta)
        saldo_final = saldo_ant + ent_mes - sai_mes

        if saldo_ant != 0 or ent_mes > 0 or sai_mes > 0 or saldo_final != 0:
            saldos_fundos.append({
                "conta": conta,
                "saldo_anterior": saldo_ant,
                "entradas": ent_mes,
                "saidas": sai_mes,
                "saldo_atual": saldo_final
            })

    saldo_operacional = total_entradas - total_saidas

    return render_template(
        "financeiro/balancete.html",
        igreja=igreja,
        mes=mes,
        ano=ano,
        nome_mes=nome_mes,
        entradas_por_categoria=dict(entradas_por_categoria),
        saidas_por_depto=dict(saidas_por_depto),
        saidas_por_categoria=dict(saidas_por_categoria),
        total_entradas=total_entradas,
        total_saidas=total_saidas,
        saldo_operacional=saldo_operacional,
        saldos_fundos=saldos_fundos,
        data_emissao=datetime.now()
    )


# -----------------------------
# ✏️ Edição e Exclusão de Lançamentos
# -----------------------------
@financeiro_bp.route('/editar_entrada/<int:id>', methods=['GET', 'POST'])
@login_required
@permission_required("financeiro", "edit")
def editar_entrada(id):
    entrada = db.session.get(Financeiro, id)
    if not entrada or entrada.tipo != "Entrada":
        flash("Registro não encontrado.", "danger")
        return redirect(url_for("financeiro.entradas"))

    form = EntradaForm(obj=entrada)
    form.membro_id.choices = _get_membro_choices()

    if request.method == "GET":
        form.tipo_receita.data = entrada.categoria
        form.membro_id.data = entrada.membro_id or 0

    if form.validate_on_submit():
        entrada.categoria = form.tipo_receita.data
        entrada.valor = float(form.valor.data)
        entrada.data = form.data.data
        entrada.forma_pagamento = form.forma_pagamento.data
        entrada.conta = form.conta.data
        entrada.departamento = form.departamento.data
        entrada.descricao = form.descricao.data
        entrada.observacoes = sanitizar_html(form.observacoes.data) if form.observacoes.data else None

        membro_sel = form.membro_id.data if form.membro_id.data and form.membro_id.data > 0 else None
        entrada.membro_id = membro_sel
        if membro_sel:
            m = db.session.get(Member, membro_sel)
            entrada.cpf_membro = m.cpf if m else None

        if form.comprovante.data:
            novo_path = UploadService.save_image(form.comprovante.data, subfolder="financeiro")
            if novo_path:
                entrada.comprovante = novo_path

        db.session.commit()
        registrar_log(current_user.nome, f"Editou entrada: {entrada.descricao}", "sucesso")
        flash("Entrada atualizada com sucesso!", "success")
        return redirect(url_for("financeiro.entradas"))

    return render_template("financeiro/editar_entrada.html", form=form, entrada=entrada)


@financeiro_bp.route('/saidas/editar/<int:id>', methods=['GET', 'POST'])
@login_required
@permission_required("financeiro", "edit")
def editar_saida(id):
    saida = db.session.get(Financeiro, id)
    if not saida or saida.tipo != "Saída":
        flash("Registro inválido para edição.", "danger")
        return redirect(url_for('financeiro.saidas'))

    form = SaidaForm(obj=saida)
    if form.validate_on_submit():
        saida.categoria = form.categoria.data
        saida.departamento = form.departamento.data
        saida.valor = float(form.valor.data)
        saida.data = form.data.data
        saida.forma_pagamento = form.forma_pagamento.data
        saida.conta = form.conta.data
        saida.cnpj_fornecedor = form.cnpj_fornecedor.data
        saida.descricao = form.descricao.data
        saida.observacoes = sanitizar_html(form.observacoes.data) if form.observacoes.data else None

        if form.comprovante.data:
            novo_path = UploadService.save_image(form.comprovante.data, subfolder="financeiro")
            if novo_path:
                saida.comprovante = novo_path

        db.session.commit()
        registrar_log(current_user.nome, f"Editou saída: {saida.descricao}", "sucesso")
        flash("Saída atualizada com sucesso!", "success")
        return redirect(url_for('financeiro.saidas'))

    return render_template('financeiro/editar_saida.html', form=form, saida=saida)


@financeiro_bp.route('/excluir/<int:id>', methods=['POST'])
@login_required
@permission_required("financeiro", "delete")
def excluir_lancamento(id):
    item = db.session.get(Financeiro, id)
    if not item:
        flash("Lançamento não encontrado.", "danger")
        return redirect(url_for("financeiro.financeiro"))

    tipo = item.tipo
    desc = item.descricao or item.categoria
    if item.comprovante:
        UploadService.delete_file(item.comprovante)

    db.session.delete(item)
    db.session.commit()
    registrar_log(current_user.nome, f"Excluiu {tipo.lower()}: {desc}", "sucesso")
    flash(f"{tipo} excluída com sucesso!", "success")

    if tipo == "Entrada":
        return redirect(url_for("financeiro.entradas"))
    return redirect(url_for("financeiro.saidas"))


# -----------------------------
# 📄 Relatórios & Exportação
# -----------------------------
@financeiro_bp.route('/relatorios', methods=['GET', 'POST'])
@login_required
@permission_required("financeiro", "view")
def relatorios():
    form = FiltroRelatorioForm()
    query = Financeiro.query

    if form.validate_on_submit() or request.args.get("filtrar"):
        dt_ini = form.inicio.data or _parse_filter_date(request.args.get("inicio"))
        dt_fim = form.fim.data or _parse_filter_date(request.args.get("fim"))
        tipo = form.tipo.data or request.args.get("tipo")
        categoria = form.categoria.data or request.args.get("categoria")
        conta = form.conta.data or request.args.get("conta")
        departamento = form.departamento.data or request.args.get("departamento")

        if dt_ini:
            query = query.filter(Financeiro.data >= dt_ini)
        if dt_fim:
            query = query.filter(Financeiro.data <= dt_fim)
        if tipo:
            query = query.filter(Financeiro.tipo == tipo)
        if categoria:
            query = query.filter(Financeiro.categoria == categoria)
        if conta:
            query = query.filter(Financeiro.conta == conta)
        if departamento:
            query = query.filter(Financeiro.departamento == departamento)

    page = request.args.get("page", 1, type=int)
    registros = query.order_by(Financeiro.data.desc()).paginate(page=page, per_page=15, error_out=False)

    todos_filtrados = query.all()
    total_entradas = sum(r.valor for r in todos_filtrados if r.tipo == "Entrada")
    total_saidas = sum(r.valor for r in todos_filtrados if r.tipo == "Saída")
    saldo_filtrado = total_entradas - total_saidas

    por_categoria = defaultdict(float)
    for r in todos_filtrados:
        por_categoria[r.categoria] += float(r.valor)

    categorias_labels = list(por_categoria.keys())
    categorias_data = [por_categoria[c] for c in categorias_labels]

    return render_template(
        'financeiro/relatorios.html',
        form=form,
        registros=registros,
        total_entradas=total_entradas,
        total_saidas=total_saidas,
        saldo_filtrado=saldo_filtrado,
        categorias_labels=categorias_labels,
        categorias_data=categorias_data
    )


@financeiro_bp.route('/export.csv')
@login_required
@permission_required("financeiro", "view")
def export_csv():
    inicio_str = request.args.get('inicio')
    fim_str = request.args.get('fim')
    tipo = request.args.get('tipo')
    categoria = request.args.get('categoria')

    query = Financeiro.query
    if inicio_str:
        dt_inicio = _parse_filter_date(inicio_str)
        if dt_inicio:
            query = query.filter(Financeiro.data >= dt_inicio)
    if fim_str:
        dt_fim = _parse_filter_date(fim_str)
        if dt_fim:
            query = query.filter(Financeiro.data <= dt_fim)
    if tipo:
        query = query.filter(Financeiro.tipo == tipo)
    if categoria:
        query = query.filter(Financeiro.categoria.ilike(f"%{categoria}%"))

    registros = query.order_by(Financeiro.data.asc()).all()

    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow([
        "Data", "Tipo", "Categoria", "Departamento", "Conta / Fundo",
        "Forma de Pagamento", "Descrição", "Valor (R$)", "Membro Contribuinte", "CNPJ / Fornecedor", "Lançado Por"
    ])
    for r in registros:
        writer.writerow([
            r.data.strftime("%d/%m/%Y") if r.data else "",
            r.tipo,
            r.categoria,
            r.departamento,
            r.conta,
            r.forma_pagamento,
            r.descricao or "",
            f"{r.valor:.2f}",
            r.membro.nome if r.membro else (r.cpf_membro or ""),
            r.cnpj_fornecedor or "",
            r.usuario or ""
        ])

    registrar_log(current_user.nome, "Exportou relatório financeiro completo em CSV", "sucesso")
    return Response(
        output.getvalue(),
        mimetype='text/csv; charset=utf-8',
        headers={"Content-Disposition": "attachment; filename=livro_caixa_igreja.csv"}
    )


# -----------------------------
# 📁 Galeria de Comprovantes
# -----------------------------
@financeiro_bp.route('/comprovantes', methods=['GET'])
@login_required
@permission_required("financeiro", "view")
def comprovantes():
    filtro = request.args.get("filtro", "").strip()
    query = Financeiro.query.filter(Financeiro.comprovante.isnot(None))

    if filtro:
        query = query.filter(
            or_(
                Financeiro.descricao.ilike(f"%{filtro}%"),
                Financeiro.categoria.ilike(f"%{filtro}%")
            )
        )

    page = request.args.get("page", 1, type=int)
    registros = query.order_by(Financeiro.data.desc()).paginate(page=page, per_page=12, error_out=False)

    por_mes = defaultdict(list)
    for r in registros.items:
        chave = r.data.strftime("%m/%Y")
        por_mes[chave].append(r)

    return render_template(
        "financeiro/comprovantes.html",
        por_mes=dict(por_mes),
        pagination=registros,
        filtro=filtro
    )
