from .user import User, Permission, UserPermission
from .member import Member, PublicLink
from .evento import Evento
from .financeiro import Financeiro
from .patrimonio import Patrimonio
from .log import Log
from .documento import Ata, Certificado, Carta
from .igreja import Igreja  
from .ebd import EbdConfig, EbdPeriodo, EbdClasse, EbdProfessor, EbdMatricula, EbdAula, EbdFrequencia
from .escala import Equipe, EquipeFuncao, EquipeMembro, Escala, EscalaItem

# Exportação unificada dos modelos do SiGI
__all__ = [
    "User", "Permission", "UserPermission",
    "Member", "PublicLink", "Evento", "Financeiro",
    "Patrimonio", "Log", "Ata", "Certificado", "Carta", "Igreja",
    "EbdConfig", "EbdPeriodo", "EbdClasse", "EbdProfessor",
    "EbdMatricula", "EbdAula", "EbdFrequencia",
    "Equipe", "EquipeFuncao", "EquipeMembro", "Escala", "EscalaItem"
]

