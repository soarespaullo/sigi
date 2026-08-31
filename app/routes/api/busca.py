import unicodedata
from flask import request, jsonify, url_for
from flask_login import login_required, current_user
from sqlalchemy import or_

from app.extensions import db
from app.models import Member, User, Financeiro
from app.models.patrimonio import Patrimonio
from app.models.evento import Evento
from app.models.documento import Ata, Certificado, Carta
from . import api_bp


def remover_acentos(texto: str) -> str:
    """Remove acentos e caracteres diacríticos para busca tolerante a acentuação."""
    if not texto:
        return ""
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join([c for c in nfkd if not unicodedata.combining(c)]).lower().strip()


# ---------------------------------------------------------------------------
# 👥 Busca de Membros & Pessoas
# ---------------------------------------------------------------------------
@api_bp.route("/busca/membros", methods=["GET"])
@login_required
def buscar_membros():
    termo = request.args.get("q", "").strip()
    status_filtro = request.args.get("status", "Ativo")
    limite = min(request.args.get("limit", 10, type=int), 50)

    if not termo or len(termo) < 2:
        return jsonify([])

    termo_norm = remover_acentos(termo)
    query = Member.query

    # Filtro de Status
    if status_filtro == "Ativo":
        query = query.filter(
            (Member.status.is_(None)) | (Member.status == "Ativo")
        ).filter(Member.data_saida.is_(None))
    elif status_filtro == "Inativo":
        query = query.filter(
            (Member.status == "Inativo") | (Member.data_saida.isnot(None))
        )
    elif status_filtro == "Transferido":
        query = query.filter(Member.status == "Transferido")

    # Condições de busca especializadas por tipo de dado
    condicoes = []
    
    # 1. Busca por início de Nome (Regra Principal Global: WHERE nome LIKE 'Termo%')
    # Usamos o prefixo das 2 primeiras letras para garantir captura no banco mesmo com acentuação
    prefixo_2 = termo_norm[:2]
    condicoes.append(Member.nome.ilike(f"{termo}%"))
    condicoes.append(Member.nome.ilike(f"{prefixo_2}%"))

    # 2. Se o termo for e-mail (contém @)
    if "@" in termo:
        condicoes.append(Member.email.ilike(f"{termo}%"))

    # 3. Se o termo for documento ou telefone (somente se a busca for primariamente numérica)
    termo_limpo = termo.replace(".", "").replace("-", "").replace("/", "").replace(" ", "").replace("(", "").replace(")", "")
    if termo_limpo.isdigit() and len(termo_limpo) >= 3:
        condicoes.append(Member.cpf.ilike(f"%{termo_limpo}%"))
        condicoes.append(Member.telefone.ilike(f"%{termo_limpo}%"))

    membros = query.filter(or_(*condicoes)).order_by(Member.nome.asc()).limit(limite * 4).all()

    # Refinamento estrito em memória para garantir acentuação e início do nome
    partes_termo = termo_norm.split()
    resultados = []
    
    for m in membros:
        nome_norm = remover_acentos(m.nome)
        
        # O nome principal deve começar com o primeiro termo pesquisado
        match_nome = False
        if len(partes_termo) == 1:
            match_nome = nome_norm.startswith(termo_norm)
        else:
            # Termos múltiplos (ex: "Maria San"): primeiro nome começa com 'maria' e palavras seguintes batem
            primeira_palavra = partes_termo[0]
            if nome_norm.startswith(primeira_palavra):
                match_nome = all(parte in nome_norm for parte in partes_termo[1:])

        # Outros identificadores específicos (apenas quando semanticamente aplicável)
        match_email = "@" in termo and (m.email or "").lower().startswith(termo.lower())
        match_doc = termo_limpo.isdigit() and len(termo_limpo) >= 3 and (termo_limpo in "".join(filter(str.isdigit, m.cpf or "")) or termo_limpo in "".join(filter(str.isdigit, m.telefone or "")))

        if match_nome or match_email or match_doc:
            foto_url = None
            if m.foto:
                filename = m.foto if m.foto.startswith("uploads/") else f"uploads/{m.foto}"
                foto_url = url_for("static", filename=filename)

            inicial = m.nome[0].upper() if m.nome else "?"

            subtext_parts = []
            if m.funcao:
                subtext_parts.append(m.funcao)
            if m.status:
                subtext_parts.append(m.status)
            if m.telefone:
                subtext_parts.append(m.telefone)

            resultados.append({
                "id": m.id,
                "value": m.id,
                "label": m.nome,
                "subtext": " • ".join(subtext_parts) if subtext_parts else "Membro da Igreja",
                "funcao": m.funcao or "Membro",
                "status": m.status or "Ativo",
                "foto": foto_url,
                "inicial": inicial,
                "telefone": m.telefone or "",
                "email": m.email or "",
            })

            if len(resultados) >= limite:
                break

    return jsonify(resultados)


# ---------------------------------------------------------------------------
# 📦 Busca de Patrimônios
# ---------------------------------------------------------------------------
@api_bp.route("/busca/patrimonios", methods=["GET"])
@login_required
def buscar_patrimonios():
    termo = request.args.get("q", "").strip()
    limite = min(request.args.get("limit", 10, type=int), 50)

    if not termo or len(termo) < 2:
        return jsonify([])

    termo_norm = remover_acentos(termo)
    itens = Patrimonio.query.filter(
        or_(
            Patrimonio.nome.ilike(f"{termo}%"),
            Patrimonio.nome.ilike(f"{termo_norm}%"),
            Patrimonio.numero.ilike(f"{termo}%"),
            Patrimonio.categoria.ilike(f"{termo}%"),
        )
    ).order_by(Patrimonio.nome.asc()).limit(limite).all()

    resultados = []
    for item in itens:
        resultados.append({
            "id": item.id,
            "value": item.id,
            "label": item.nome,
            "subtext": f"Nº: {item.numero or '-'} • Categoria: {item.categoria or '-'} • Situação: {item.situacao or 'Ativo'}",
            "categoria": item.categoria or "",
            "numero": item.numero or "",
            "situacao": item.situacao or "Ativo",
        })

    return jsonify(resultados)


# ---------------------------------------------------------------------------
# 📅 Busca de Eventos
# ---------------------------------------------------------------------------
@api_bp.route("/busca/eventos", methods=["GET"])
@login_required
def buscar_eventos():
    termo = request.args.get("q", "").strip()
    limite = min(request.args.get("limit", 10, type=int), 50)

    if not termo or len(termo) < 2:
        return jsonify([])

    termo_norm = remover_acentos(termo)
    eventos = Evento.query.filter(
        or_(
            Evento.titulo.ilike(f"{termo}%"),
            Evento.titulo.ilike(f"{termo_norm}%"),
            Evento.tipo.ilike(f"{termo}%"),
            Evento.organizador.ilike(f"{termo}%"),
        )
    ).order_by(Evento.data_inicio.desc()).limit(limite).all()

    resultados = []
    for ev in eventos:
        data_str = ev.data_inicio.strftime("%d/%m/%Y") if ev.data_inicio else ""
        resultados.append({
            "id": ev.id,
            "value": ev.id,
            "label": ev.titulo,
            "subtext": f"Data: {data_str} • Tipo: {ev.tipo or '-'} • Org: {ev.organizador or '-'}",
            "tipo": ev.tipo or "",
            "data": data_str,
            "status": ev.status or "Confirmado",
        })

    return jsonify(resultados)


# ---------------------------------------------------------------------------
# 💰 Busca de Entradas (Receitas Financeiras)
# ---------------------------------------------------------------------------
@api_bp.route("/busca/entradas", methods=["GET"])
@login_required
def buscar_entradas():
    termo = request.args.get("q", "").strip()
    limite = min(request.args.get("limit", 10, type=int), 50)

    if not termo or len(termo) < 2:
        return jsonify([])

    termo_norm = remover_acentos(termo)
    prefixo_2 = termo_norm[:2]

    # Busca registros que comecem com o termo na descrição, conta, categoria ou no nome do membro
    entradas = Financeiro.query.outerjoin(Member).filter(
        Financeiro.tipo == "Entrada",
        or_(
            Member.nome.ilike(f"{termo}%"),
            Member.nome.ilike(f"{prefixo_2}%"),
            Financeiro.descricao.ilike(f"{termo}%"),
            Financeiro.descricao.ilike(f"{prefixo_2}%"),
            Financeiro.categoria.ilike(f"{termo}%"),
            Financeiro.conta.ilike(f"{termo}%"),
            Financeiro.forma_pagamento.ilike(f"{termo}%"),
        )
    ).order_by(Financeiro.data.desc(), Financeiro.id.desc()).limit(limite * 3).all()

    resultados = []
    vistos = set()

    for item in entradas:
        data_str = item.data.strftime("%d/%m/%Y") if item.data else ""
        
        # 1. Se a busca deu match no nome do membro vinculado
        membro_match = False
        if item.membro:
            nome_membro_norm = remover_acentos(item.membro.nome)
            if nome_membro_norm.startswith(termo_norm) or any(p.startswith(termo_norm) for p in nome_membro_norm.split()):
                membro_match = True

        if membro_match and item.membro:
            label = item.membro.nome
            chave = f"membro_{item.membro.id}"
            if chave in vistos:
                continue
            vistos.add(chave)

            foto_url = None
            if item.membro.foto:
                filename = item.membro.foto if item.membro.foto.startswith("uploads/") else f"uploads/{item.membro.foto}"
                foto_url = url_for("static", filename=filename)

            resultados.append({
                "id": item.id,
                "value": label,
                "label": label,
                "subtext": f"{item.categoria} • {item.conta} • {data_str}",
                "categoria": item.categoria or "Receita",
                "foto": foto_url,
                "inicial": item.membro.nome[0].upper(),
                "status": f"R$ {item.valor:.2f}",
            })
        else:
            # 2. Se a busca deu match na descrição, conta ou categoria
            desc_norm = remover_acentos(item.descricao or "")
            cat_norm = remover_acentos(item.categoria or "")
            conta_norm = remover_acentos(item.conta or "")

            if (desc_norm.startswith(termo_norm) or cat_norm.startswith(termo_norm) or conta_norm.startswith(termo_norm) or termo_norm in desc_norm):
                label = item.descricao if desc_norm.startswith(termo_norm) else (item.categoria if cat_norm.startswith(termo_norm) else (item.descricao or item.categoria))
                chave = f"desc_{label}"
                if chave in vistos:
                    continue
                vistos.add(chave)

                membro_info = f" • {item.membro.nome}" if item.membro else ""
                resultados.append({
                    "id": item.id,
                    "value": label,
                    "label": label,
                    "subtext": f"{item.categoria} • {item.conta} • {data_str}{membro_info}",
                    "categoria": item.categoria or "Receita",
                    "foto": None,
                    "inicial": label[0].upper() if label else "R",
                    "status": f"R$ {item.valor:.2f}",
                })

        if len(resultados) >= limite:
            break

    return jsonify(resultados)


# ---------------------------------------------------------------------------
# 💸 Busca de Saídas (Despesas Financeiras)
# ---------------------------------------------------------------------------
@api_bp.route("/busca/saidas", methods=["GET"])
@login_required
def buscar_saidas():
    termo = request.args.get("q", "").strip()
    limite = min(request.args.get("limit", 10, type=int), 50)

    if not termo or len(termo) < 2:
        return jsonify([])

    termo_norm = remover_acentos(termo)
    prefixo_2 = termo_norm[:2]

    saidas = Financeiro.query.filter(
        Financeiro.tipo == "Saída",
        or_(
            Financeiro.descricao.ilike(f"{termo}%"),
            Financeiro.descricao.ilike(f"{prefixo_2}%"),
            Financeiro.categoria.ilike(f"{termo}%"),
            Financeiro.departamento.ilike(f"{termo}%"),
            Financeiro.conta.ilike(f"{termo}%"),
            Financeiro.cnpj_fornecedor.ilike(f"{termo}%"),
        )
    ).order_by(Financeiro.data.desc(), Financeiro.id.desc()).limit(limite * 3).all()

    resultados = []
    vistos = set()

    for item in saidas:
        data_str = item.data.strftime("%d/%m/%Y") if item.data else ""
        desc_norm = remover_acentos(item.descricao or "")
        cat_norm = remover_acentos(item.categoria or "")
        forn_norm = remover_acentos(item.cnpj_fornecedor or "")
        dep_norm = remover_acentos(item.departamento or "")

        # Se deu match no favorecido/fornecedor
        if forn_norm and (forn_norm.startswith(termo_norm) or termo_norm in forn_norm):
            label = item.cnpj_fornecedor
            chave = f"forn_{label}"
        elif desc_norm.startswith(termo_norm) or termo_norm in desc_norm:
            label = item.descricao
            chave = f"desc_{label}"
        else:
            label = item.categoria or item.departamento
            chave = f"cat_{label}"

        if chave in vistos:
            continue
        vistos.add(chave)

        forn_str = f" • {item.cnpj_fornecedor}" if item.cnpj_fornecedor and label != item.cnpj_fornecedor else ""
        resultados.append({
            "id": item.id,
            "value": label,
            "label": label,
            "subtext": f"{item.categoria} • {item.departamento} • {data_str}{forn_str}",
            "categoria": item.categoria or "Despesa",
            "foto": None,
            "inicial": label[0].upper() if label else "D",
            "status": f"R$ {item.valor:.2f}",
        })

        if len(resultados) >= limite:
            break

    return jsonify(resultados)
