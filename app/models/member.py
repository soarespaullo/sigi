from app.extensions import db
import secrets
from datetime import datetime, date, timezone

# -----------------------------
# 👥 Membros da Igreja
# -----------------------------
class Member(db.Model):
    __tablename__ = "members"

    id = db.Column(db.Integer, primary_key=True)

    # Dados pessoais
    foto = db.Column(db.String(200))
    nome = db.Column(db.String(120), nullable=False)
    data_nascimento = db.Column(db.Date, nullable=True)
    sexo = db.Column(db.String(20))
    estado_civil = db.Column(db.String(20))
    conjuge = db.Column(db.String(120))
    telefone = db.Column(db.String(20))
    email = db.Column(db.String(120))

    # Endereço
    endereco = db.Column(db.String(200))
    bairro = db.Column(db.String(100))
    cep = db.Column(db.String(20))

    # Igreja
    batizado = db.Column(db.Boolean, nullable=True)
    dizimista = db.Column(db.Boolean, nullable=True)
    data_batismo = db.Column(db.Date, nullable=True)
    funcao = db.Column(db.String(50))
    status = db.Column(db.String(20))
    data_cadastro = db.Column(db.Date, nullable=True)
    numero_carteira = db.Column(db.String(50))
    igreja_local = db.Column(db.String(120))
    validade = db.Column(db.Date, nullable=True)

    # ➕ Novos campos
    data_conversao = db.Column(db.Date, nullable=True)
    data_saida = db.Column(db.Date, nullable=True)
    visitante = db.Column(db.Boolean, default=False)   # ✅ novo campo

    # Documentos
    nacionalidade = db.Column(db.String(50))
    naturalidade = db.Column(db.String(50))
    rg = db.Column(db.String(20))
    cpf = db.Column(db.String(20))
    pai = db.Column(db.String(120))
    mae = db.Column(db.String(120))
    filiacao = db.Column(db.String(200))

    # Observações
    observacoes = db.Column(db.Text)

    @property
    def idade(self):
        """Calcula a idade com base na data de nascimento."""
        if self.data_nascimento:
            hoje = date.today()
            anos = hoje.year - self.data_nascimento.year
            if (hoje.month, hoje.day) < (self.data_nascimento.month, self.data_nascimento.day):
                anos -= 1
            return anos
        return None

    @property
    def ativo(self):
        """Retorna True se o membro estiver ativo (sem data de saída e com status 'Ativo' ou padrão), False caso contrário."""
        return self.data_saida is None and (self.status is None or self.status == "Ativo")

    def __repr__(self):
        return f"<Member {self.nome}>"

# -----------------------------
# 🔗 Links Públicos (ex: cadastro de visitantes)
# -----------------------------
class PublicLink(db.Model):
    __tablename__ = "public_links"

    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(50))  # ex: "visitante"
    hash = db.Column(db.String(64), unique=True, nullable=False)
    ativo = db.Column(db.Boolean, default=True)
    data_criacao = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    @staticmethod
    def gerar_hash():
        return secrets.token_hex(16)

    def __repr__(self):
        return f"<PublicLink {self.tipo} - {self.hash}>"
