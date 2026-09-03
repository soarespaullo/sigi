from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import current_user
from app.models import User, Permission, UserPermission
from app.extensions import db
from .forms import PermissoesForm
from app.decorators import permission_required

# Blueprint de Permissões
permissoes_bp = Blueprint("permissoes", __name__, url_prefix="/permissoes")

@permissoes_bp.route("/", methods=["GET", "POST"])
@permission_required("config", "view")   # 🔹 admin sempre tem acesso
def permissoes_page():
    # Lista todos os usuários
    usuarios = User.query.all()

    # Instancia o formulário
    form = PermissoesForm()
    form.usuario_id.choices = [(u.id, f"{u.nome or u.email}") for u in usuarios]

    # Mapeamento entre campos do form e permissões no banco
    mapping = {
        # Usuários
        "usuarios_view": ("usuarios", "view"),
        "usuarios_create": ("usuarios", "create"),  
        "usuarios_edit": ("usuarios", "edit"),
        "usuarios_delete": ("usuarios", "delete"),

        # Configurações
        "config_view": ("config", "view"),
        "config_edit": ("config", "edit"),
        "config_delete": ("config", "delete"),

        # Mail / Email
        "mail_view": ("mail", "view"),
        "mail_create": ("mail", "create"),        
        "mail_edit": ("mail", "edit"),
        "mail_delete": ("mail", "delete"),

        # Financeiro
        "financeiro_view": ("financeiro", "view"),
        "financeiro_create": ("financeiro", "create"),
        "financeiro_edit": ("financeiro", "edit"),
        "financeiro_delete": ("financeiro", "delete"),

        # Atas
        "atas_view": ("atas", "view"),
        "atas_create": ("atas", "create"),
        "atas_edit": ("atas", "edit"),
        "atas_delete": ("atas", "delete"),

        # Cartas
        "cartas_view": ("cartas", "view"),
        "cartas_create": ("cartas", "create"),
        "cartas_edit": ("cartas", "edit"),
        "cartas_delete": ("cartas", "delete"),

        # Certificados
        "certificados_view": ("certificados", "view"),
        "certificados_create": ("certificados", "create"),
        "certificados_edit": ("certificados", "edit"),
        "certificados_delete": ("certificados", "delete"),

        # Eventos
        "eventos_view": ("eventos", "view"),
        "eventos_create": ("eventos", "create"),
        "eventos_edit": ("eventos", "edit"),
        "eventos_delete": ("eventos", "delete"),

        # Membros
        "membros_view": ("membros", "view"),
        "membros_create": ("membros", "create"),
        "membros_edit": ("membros", "edit"),
        "membros_delete": ("membros", "delete"),

        # Patrimônios
        "patrimonios_view": ("patrimonios", "view"),
        "patrimonios_create": ("patrimonios", "create"),
        "patrimonios_edit": ("patrimonios", "edit"),
        "patrimonios_delete": ("patrimonios", "delete"),

        # Escola Dominical (EBD)
        "ebd_view": ("ebd", "view"),
        "ebd_create": ("ebd", "create"),
        "ebd_edit": ("ebd", "edit"),
        "ebd_delete": ("ebd", "delete"),
        "ebd_frequencia": ("ebd", "frequencia"),

        # Escalas de Obreiros e Voluntários
        "escalas_view": ("escalas", "view"),
        "escalas_create": ("escalas", "create"),
        "escalas_edit": ("escalas", "edit"),
        "escalas_delete": ("escalas", "delete"),
        "escalas_gerenciar": ("escalas", "gerenciar"),

        # Perfil
        "perfil_view": ("perfil", "view"),
        "perfil_password": ("perfil", "password"),
    }

    # 🔹 Captura o usuário selecionado (GET ou POST)
    usuario_id = request.args.get("usuario_id", type=int) or form.usuario_id.data

    # Se o formulário foi enviado
    if form.validate_on_submit():
        usuario_id = form.usuario_id.data

        # Remove permissões antigas do usuário
        UserPermission.query.filter_by(user_id=usuario_id).delete()

        # Adiciona as novas permissões marcadas
        for field_name, (area, action) in mapping.items():
            if getattr(form, field_name).data:  # se checkbox marcado
                perm = Permission.query.filter_by(area=area, action=action).first()
                if perm:
                    db.session.add(UserPermission(user_id=usuario_id, permission_id=perm.id))

        db.session.commit()
        flash("Permissões atualizadas com sucesso!", "success")

        # Redirect mantendo o usuário selecionado
        return redirect(url_for("configuracoes.permissoes.permissoes_page", usuario_id=usuario_id))

    # 🔹 Pré-carregar permissões já existentes
    if usuario_id:
        form.usuario_id.data = usuario_id
        user_perms = UserPermission.query.filter_by(user_id=usuario_id).all()
        user_perm_ids = {up.permission_id for up in user_perms}

        for field_name, (area, action) in mapping.items():
            perm = Permission.query.filter_by(area=area, action=action).first()
            if perm and perm.id in user_perm_ids:
                getattr(form, field_name).data = True

    return render_template("configuracoes/permissoes.html", usuarios=usuarios, form=form)
