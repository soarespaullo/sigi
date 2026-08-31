from .auth import auth_bp
from .dashboard import dashboard_bp
from .event import event_bp
from .financeiro import financeiro_bp
from .member import member_bp
from .patrimonio import patrimonio_bp
from .configuracoes import config_bp
from .perfil.perfil import perfil_bp
from .documentos import documentos_bp
from .api import api_bp

__all__ = [
    "auth_bp",
    "dashboard_bp",
    "event_bp",
    "financeiro_bp",
    "member_bp",
    "patrimonio_bp",
    "config_bp",
    "perfil_bp",
    "documentos_bp",
    "api_bp",
]
