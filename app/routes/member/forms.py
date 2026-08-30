from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, SelectField, TextAreaField, DateField, SubmitField
from wtforms.validators import DataRequired, Optional, Email
from datetime import date

class MemberForm(FlaskForm):
    foto = FileField(
        "Foto",
        validators=[
            Optional(),
            FileAllowed(["jpg", "jpeg", "png"], "Somente imagens JPG ou PNG são permitidas.")
        ]
    )
    nome = StringField("Nome", validators=[DataRequired()])
    data_nascimento = DateField("Data de Nascimento", format="%Y-%m-%d", validators=[Optional()])
    sexo = SelectField("Sexo", choices=[("Masculino", "Masculino"), ("Feminino", "Feminino")], validators=[Optional()])
    estado_civil = SelectField("Estado Civil", choices=[
        ("Solteiro", "Solteiro"),
        ("Casado", "Casado"),
        ("Divorciado", "Divorciado"),
        ("Viúvo", "Viúvo")
    ], validators=[Optional()])
    conjuge = StringField("Nome do Cônjuge", validators=[Optional()])

    telefone = StringField("Telefone", validators=[Optional()])
    email = StringField("Email", validators=[Optional(), Email()])
    endereco = StringField("Endereço", validators=[Optional()])
    bairro = StringField("Bairro", validators=[Optional()])
    cep = StringField("CEP", validators=[Optional()])

    batizado = SelectField(
        "Batizado",
        coerce=lambda v: v == "True",
        choices=[("True", "Sim"), ("False", "Não")],
        validators=[Optional()]
    )
    dizimista = SelectField(
        "Dizimista",
        coerce=lambda v: v == "True",
        choices=[("True", "Sim"), ("False", "Não")],
        validators=[Optional()]
    )

    data_batismo = DateField("Data de Batismo", format="%Y-%m-%d", validators=[Optional()])

    funcao = SelectField("Função", choices=[
        ("Membro", "Membro"),
        ("Diácono", "Diácono"),
        ("Presbítero", "Presbítero"),
        ("Pastor", "Pastor"),
        ("Visitante", "Visitante")   # ✅ nova opção adicionada
    ], validators=[Optional()])

    status = SelectField("Status", choices=[
        ("Ativo", "Ativo"),
        ("Inativo", "Inativo"),
        ("Transferido", "Transferido")
    ], validators=[Optional()])
    # data_cadastro = DateField("Data de Cadastro", format="%Y-%m-%d", validators=[Optional()])
    # ✅ já vem preenchido com a data atual, mas pode ser alterado
    data_cadastro = DateField("Data de Cadastro", format="%Y-%m-%d", default=date.today, validators=[Optional()])
    numero_carteira = StringField("Número da Carteira", validators=[Optional()])
    igreja_local = StringField("Igreja Local", validators=[Optional()])
    validade = DateField("Validade da Carteira", format="%Y-%m-%d", validators=[Optional()])

    # ➕ Novos campos
    data_conversao = DateField("Data de Conversão", format="%Y-%m-%d", validators=[Optional()])
    data_saida = DateField("Data de Saída", format="%Y-%m-%d", validators=[Optional()])

    nacionalidade = StringField("Nacionalidade", validators=[Optional()])
    naturalidade = StringField("Naturalidade", validators=[Optional()])
    rg = StringField("RG", validators=[Optional()])
    cpf = StringField("CPF", validators=[Optional()])
    pai = StringField("Pai", validators=[Optional()])
    mae = StringField("Mãe", validators=[Optional()])
    filiacao = StringField("Filiação", validators=[Optional()])

    observacoes = TextAreaField("Observações", validators=[Optional()])
    submit = SubmitField("Salvar")
