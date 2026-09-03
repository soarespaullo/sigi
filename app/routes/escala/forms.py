from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, BooleanField, IntegerField, DateField, SubmitField
from wtforms.validators import DataRequired, Length, Optional


class EscalaForm(FlaskForm):
    titulo = StringField("Título da Escala", validators=[DataRequired(message="Informe o título da escala."), Length(max=150)])
    data = DateField("Data", format="%Y-%m-%d", validators=[DataRequired(message="Informe a data da escala.")])
    hora_inicio = StringField("Horário de Início", validators=[DataRequired(message="Informe o horário inicial."), Length(max=10)], default="18:00")
    hora_fim = StringField("Horário de Término", validators=[Optional(), Length(max=10)], default="20:30")
    evento_id = SelectField("Vincular a Culto / Evento Oficial", coerce=int, validators=[Optional()])
    local = StringField("Local", validators=[Optional(), Length(max=150)], default="Templo Principal")
    observacoes = TextAreaField("Observações Gerais / Instruções para os Voluntários", validators=[Optional()])
    status = SelectField(
        "Status da Escala",
        choices=[
            ("rascunho", "Rascunho (Em elaboração)"),
            ("publicada", "Publicada (Visível aos voluntários)"),
            ("confirmada", "Confirmada (Equipes completas)"),
            ("concluida", "Concluída (Realizada)"),
            ("cancelada", "Cancelada")
        ],
        default="rascunho"
    )
    submit = SubmitField("Salvar Escala")


class EquipeForm(FlaskForm):
    nome = StringField("Nome da Equipe / Departamento", validators=[DataRequired(message="Informe o nome da equipe."), Length(max=100)])
    descricao = TextAreaField("Descrição do Ministério / Atribuições", validators=[Optional()])
    cor = StringField("Cor Identificadora (Hexadecimal)", validators=[Optional(), Length(max=20)], default="#0d6efd")
    icone = StringField("Ícone Bootstrap Icons (ex: bi-music-note, bi-camera-video)", validators=[Optional(), Length(max=50)], default="bi-people")
    lider_id = SelectField("Líder Responsável", coerce=int, validators=[Optional()])
    ativo = BooleanField("Equipe Ativa", default=True)
    submit = SubmitField("Salvar Equipe")


class EquipeFuncaoForm(FlaskForm):
    nome = StringField("Nome da Função / Papel", validators=[DataRequired(message="Informe a função."), Length(max=100)])
    descricao = StringField("Descrição / Atribuições", validators=[Optional(), Length(max=255)])
    ordem = IntegerField("Ordem de Exibição", default=0, validators=[Optional()])
    ativo = BooleanField("Ativo", default=True)
    submit = SubmitField("Salvar Função")


class EquipeMembroForm(FlaskForm):
    membro_id = SelectField("Selecionar Membro / Voluntário", coerce=int, validators=[DataRequired(message="Selecione um membro.")])
    funcao_padrao_id = SelectField("Função Principal na Equipe", coerce=int, validators=[Optional()])
    submit = SubmitField("Adicionar à Equipe")


class AdicionarVoluntarioForm(FlaskForm):
    equipe_id = SelectField("Equipe", coerce=int, validators=[DataRequired(message="Selecione a equipe.")])
    funcao_id = SelectField("Função / Papel", coerce=int, validators=[Optional()])
    membro_id = SelectField("Voluntário", coerce=int, validators=[DataRequired(message="Selecione o voluntário.")])
    observacao = StringField("Observação / Instrução específica", validators=[Optional(), Length(max=255)])
    submit = SubmitField("Escalar Voluntário")


class SubstituirVoluntarioForm(FlaskForm):
    novo_membro_id = SelectField("Novo Voluntário Substituto", coerce=int, validators=[DataRequired(message="Selecione o substituto.")])
    motivo = StringField("Motivo da Substituição", validators=[DataRequired(message="Informe o motivo da substituição."), Length(max=255)])
    submit = SubmitField("Confirmar Substituição")


class DuplicarEscalaForm(FlaskForm):
    nova_data = DateField("Nova Data", format="%Y-%m-%d", validators=[DataRequired(message="Informe a nova data.")])
    nova_hora_inicio = StringField("Horário de Início", validators=[DataRequired(), Length(max=10)])
    nova_hora_fim = StringField("Horário de Término", validators=[Optional(), Length(max=10)])
    novo_titulo = StringField("Novo Título (Opcional)", validators=[Optional(), Length(max=150)])
    submit = SubmitField("Duplicar Escala")
