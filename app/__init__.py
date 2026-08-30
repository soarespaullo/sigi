import os
# from flask import Flask, render_template
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_wtf.csrf import CSRFProtect
from flask_login import LoginManager
from app.extensions import db, mail, migrate
from config import get_config   # ✅ importa a função que decide o ambiente
import pytz                     # 🔹 adicionado para timezone

csrf = CSRFProtect()

def create_app(config_class=None):
    # Cria a instância do Flask
    app = Flask(__name__)
    # Usa configuração automática (production ou development conforme FLASK_ENV)
    app.config.from_object(config_class or get_config())

    # -----------------------------
    # 🔗 Inicializa extensões
    # -----------------------------
    db.init_app(app)
    mail.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    # -----------------------------
    # 🔄 Auto-migração segura de colunas (compatibilidade de schema)
    # -----------------------------
    with app.app_context():
        try:
            from sqlalchemy import text, inspect
            inspector = inspect(db.engine)
            if 'users' in inspector.get_table_names():
                colunas = [c['name'] for c in inspector.get_columns('users')]
                if 'member_id' not in colunas:
                    db.session.execute(text("ALTER TABLE users ADD COLUMN member_id INTEGER REFERENCES members(id)"))
                    db.session.commit()
        except Exception:
            pass

    # -----------------------------
    # 👤 Configuração do LoginManager
    # -----------------------------
    login_manager = LoginManager()
    login_manager.login_view = "auth.login"   # rota para redirecionar
    login_manager.login_message = "Sua sessão expirou. Faça login novamente."
    login_manager.login_message_category = "warning"
    login_manager.init_app(app)

    # 🔹 Função para carregar usuário pelo ID (compatível com SQLAlchemy 2.x)
    from app.models import User
    @login_manager.user_loader
    def load_user(user_id):
        try:
            return db.session.get(User, int(user_id))
        except (ValueError, TypeError):
            return None

    # -----------------------------
    # 📌 Importa e registra os Blueprints
    # -----------------------------
    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.event import event_bp
    from app.routes.financeiro import financeiro_bp
    from app.routes.member import member_bp
    from app.routes.patrimonio import patrimonio_bp
    from app.routes.configuracoes import config_bp
    from app.routes.perfil.perfil import perfil_bp
    from app.routes.documentos import documentos_bp
    from app.routes.ebd import ebd_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(event_bp)
    app.register_blueprint(financeiro_bp)
    app.register_blueprint(member_bp)
    app.register_blueprint(patrimonio_bp)
    app.register_blueprint(config_bp)
    app.register_blueprint(perfil_bp)
    app.register_blueprint(documentos_bp)
    app.register_blueprint(ebd_bp)
    
    # -----------------------------
    # 📅 Context processor para ano atual e timezone
    # -----------------------------
    @app.context_processor
    def inject_globals():
        from datetime import datetime
        tz_name = os.getenv("APP_TIMEZONE", "America/Sao_Paulo")
        try:
            tz = pytz.timezone(tz_name)
        except Exception:
            tz = pytz.UTC
        return {
            'current_year': datetime.now(tz).year,
            'timezone': tz
        }

    # ----------------------------- 
    # 🔐 Context processor para permissões 
    # ----------------------------- 
    @app.context_processor
    def inject_permissions():
        from app.models.permissions_helper import has_permission
        return dict(has_permission=has_permission)

    # -----------------------------
    # 💰 Filtro Jinja para formatação de moeda brasileira (R$)
    # -----------------------------
    @app.template_filter('currency')
    def format_currency_filter(value):
        if value is None:
            return "R$ 0,00"
        try:
            val = float(value)
            return f"R$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        except (ValueError, TypeError):
            return "R$ 0,00"

    # -----------------------------
    # 🕒 Filtro Jinja para converter UTC → timezone local
    # -----------------------------
    @app.template_filter('to_local')
    def to_local(dt):
        from datetime import timezone
        if dt is None:
            return dt
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        tz_name = os.getenv("APP_TIMEZONE", "America/Sao_Paulo")
        try:
            tz = pytz.timezone(tz_name)
        except Exception:
            tz = pytz.UTC
        return dt.astimezone(tz)

    # -----------------------------
    # ⚠️ Handlers globais de erro
    # -----------------------------
    from flask_wtf.csrf import CSRFError

    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        flash("Sua sessão expirou ou o formulário ficou aberto por muito tempo. Por favor, tente novamente.", "warning")
        return redirect(request.referrer or url_for("dashboard.dashboard"))

    @app.errorhandler(404)
    def page_not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(500)
    def internal_error(e):
        return render_template("errors/500.html"), 500
    
    @app.errorhandler(413)
    def request_entity_too_large(e):
        # pega o limite configurado em bytes
        max_bytes = app.config.get("MAX_CONTENT_LENGTH", 0)
        # converte para MB (arredondando)
        max_mb = int(max_bytes / (1024 * 1024))
        flash(f"Arquivo muito grande. O limite é {max_mb} MB.", "danger")
        return redirect(request.referrer or url_for("dashboard.dashboard"))

    return app
