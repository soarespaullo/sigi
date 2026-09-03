from flask_wtf import FlaskForm
from wtforms import SelectField, BooleanField, SubmitField
from wtforms.validators import DataRequired

class PermissoesForm(FlaskForm):
    usuario_id = SelectField("Usuário", coerce=int, validators=[DataRequired()])

    # Usuários
    usuarios_view = BooleanField("Visualizar Usuários")
    usuarios_create = BooleanField("Criar Usuários")        # 🔹 novo
    usuarios_edit = BooleanField("Editar Usuários")
    usuarios_delete = BooleanField("Excluir Usuários")

    # Configurações
    config_view = BooleanField("Visualizar Configurações")
    config_edit = BooleanField("Editar Configurações")
    config_delete = BooleanField("Excluir Configurações")

    # Financeiro
    financeiro_view = BooleanField("Visualizar Financeiro")
    financeiro_create = BooleanField("Criar Financeiro")
    financeiro_edit = BooleanField("Editar Financeiro")
    financeiro_delete = BooleanField("Excluir Financeiro")

    # Mail / Email
    mail_view = BooleanField("Visualizar Email")
    mail_create = BooleanField("Criar Email")               # 🔹 novo
    mail_edit = BooleanField("Editar Email")
    mail_delete = BooleanField("Excluir Email")

    # Documentos - Atas
    atas_view = BooleanField("Visualizar Atas")
    atas_create = BooleanField("Criar Atas")
    atas_edit = BooleanField("Editar Atas")
    atas_delete = BooleanField("Excluir Atas")

    # Documentos - Cartas
    cartas_view = BooleanField("Visualizar Cartas")
    cartas_create = BooleanField("Criar Cartas")
    cartas_edit = BooleanField("Editar Cartas")
    cartas_delete = BooleanField("Excluir Cartas")

    # Documentos - Certificados
    certificados_view = BooleanField("Visualizar Certificados")
    certificados_create = BooleanField("Criar Certificados")
    certificados_edit = BooleanField("Editar Certificados")
    certificados_delete = BooleanField("Excluir Certificados")

    # Eventos
    eventos_view = BooleanField("Visualizar Eventos")
    eventos_create = BooleanField("Criar Eventos")
    eventos_edit = BooleanField("Editar Eventos")
    eventos_delete = BooleanField("Excluir Eventos")

    # Membros
    membros_view = BooleanField("Visualizar Membros")
    membros_create = BooleanField("Criar Membros")
    membros_edit = BooleanField("Editar Membros")
    membros_delete = BooleanField("Excluir Membros")

    # Patrimônios
    patrimonios_view = BooleanField("Visualizar Patrimônios")
    patrimonios_create = BooleanField("Criar Patrimônios")
    patrimonios_edit = BooleanField("Editar Patrimônios")
    patrimonios_delete = BooleanField("Excluir Patrimônios")

    # Escola Dominical (EBD)
    ebd_view = BooleanField("Visualizar EBD")
    ebd_create = BooleanField("Criar EBD / Classes / Aulas")
    ebd_edit = BooleanField("Editar EBD / Classes / Aulas")
    ebd_delete = BooleanField("Excluir EBD / Classes")
    ebd_frequencia = BooleanField("Lançar / Alterar Frequência")

    # Escalas de Obreiros e Voluntários
    escalas_view = BooleanField("Visualizar Escalas")
    escalas_create = BooleanField("Criar Escalas")
    escalas_edit = BooleanField("Editar Escalas")
    escalas_delete = BooleanField("Excluir / Cancelar Escalas")
    escalas_gerenciar = BooleanField("Gerenciar Equipes, Funções & Substituições")

    # Perfil
    perfil_view = BooleanField("Visualizar Perfil")
    perfil_password = BooleanField("Alterar Senha")

    submit = SubmitField("Salvar Permissões")
