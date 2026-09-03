# app/utils/seed.py
from app.models import Permission
from app.extensions import db

def seed_permissions():
    """Popula a tabela de permissões básicas se ainda estiver vazia."""
    perms = [
        # Configurações
        ("config", "view"), ("config", "edit"), ("config", "delete"),

        # Usuários
        ("usuarios", "view"), ("usuarios", "create"), ("usuarios", "edit"), ("usuarios", "delete"),

        # Financeiro
        ("financeiro", "view"), ("financeiro", "create"), ("financeiro", "edit"), ("financeiro", "delete"),

        # Mail / Email
        ("mail", "view"), ("mail", "create"), ("mail", "edit"), ("mail", "delete"),

        # Atas
        ("atas", "view"), ("atas", "create"), ("atas", "edit"), ("atas", "delete"),

        # Cartas
        ("cartas", "view"), ("cartas", "create"), ("cartas", "edit"), ("cartas", "delete"),

        # Certificados
        ("certificados", "view"), ("certificados", "create"), ("certificados", "edit"), ("certificados", "delete"),

        # Eventos
        ("eventos", "view"), ("eventos", "create"), ("eventos", "edit"), ("eventos", "delete"),

        # Membros
        ("membros", "view"), ("membros", "create"), ("membros", "edit"), ("membros", "delete"),

        # Patrimônios
        ("patrimonios", "view"), ("patrimonios", "create"), ("patrimonios", "edit"), ("patrimonios", "delete"),

        # Escola Dominical (EBD)
        ("ebd", "view"), ("ebd", "create"), ("ebd", "edit"), ("ebd", "delete"), ("ebd", "frequencia"),

        # Escalas de Obreiros e Voluntários
        ("escalas", "view"), ("escalas", "create"), ("escalas", "edit"), ("escalas", "delete"), ("escalas", "gerenciar"),

        # Perfil
        ("perfil", "view"), ("perfil", "password"),
    ]

    adicionadas = 0
    for area, action in perms:
        if not Permission.query.filter_by(area=area, action=action).first():
            db.session.add(Permission(area=area, action=action))
            adicionadas += 1

    if adicionadas > 0:
        db.session.commit()
        print(f"[OK] {adicionadas} permissoes populadas com sucesso!")
    else:
        print("[INFO] Todas as permissoes ja existem no banco de dados.")

