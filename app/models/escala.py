import secrets
from datetime import datetime, timezone, date
from app.extensions import db

# ---------------------------------------------------------------------------
# 👥 Equipe / Departamento / Ministério
# ---------------------------------------------------------------------------
class Equipe(db.Model):
    __tablename__ = "equipes"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)  # Ex: "Louvor & Adoração", "Recepção", "Mídia"
    descricao = db.Column(db.Text, nullable=True)
    cor = db.Column(db.String(20), default="#0d6efd")  # Cor temática / badge
    icone = db.Column(db.String(50), default="bi-people")  # Ícone Bootstrap
    
    # Líder responsável da equipe (Membro)
    lider_id = db.Column(db.Integer, db.ForeignKey("members.id", ondelete="SET NULL"), nullable=True)
    lider = db.relationship("Member", foreign_keys=[lider_id], backref="equipes_lideradas")

    ativo = db.Column(db.Boolean, default=True)
    criado_em = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relacionamentos
    funcoes = db.relationship(
        "EquipeFuncao",
        backref="equipe",
        cascade="all, delete-orphan",
        order_by="EquipeFuncao.ordem.asc()",
        lazy=True
    )
    membros = db.relationship(
        "EquipeMembro",
        backref="equipe",
        cascade="all, delete-orphan",
        lazy=True
    )
    itens_escala = db.relationship(
        "EscalaItem",
        back_populates="equipe",
        cascade="all, delete-orphan",
        lazy=True
    )

    @property
    def total_voluntarios(self):
        return len([m for m in self.membros if m.ativo])

    def __repr__(self):
        return f"<Equipe {self.nome}>"


# ---------------------------------------------------------------------------
# 🎭 Funções / Papéis dentro da Equipe
# ---------------------------------------------------------------------------
class EquipeFuncao(db.Model):
    __tablename__ = "equipe_funcoes"

    id = db.Column(db.Integer, primary_key=True)
    equipe_id = db.Column(db.Integer, db.ForeignKey("equipes.id", ondelete="CASCADE"), nullable=False)
    nome = db.Column(db.String(100), nullable=False)  # Ex: "Vocal", "Violão", "Operador de Som", "Recepção"
    descricao = db.Column(db.Text, nullable=True)
    ordem = db.Column(db.Integer, default=0)
    ativo = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f"<EquipeFuncao {self.nome} ({self.equipe.nome if self.equipe else self.equipe_id})>"


# ---------------------------------------------------------------------------
# 🤝 Associação Membro ↔ Equipe (Quadro de Voluntários da Equipe)
# ---------------------------------------------------------------------------
class EquipeMembro(db.Model):
    __tablename__ = "equipe_membros"
    __table_args__ = (
        db.UniqueConstraint("equipe_id", "membro_id", name="uq_equipe_membro"),
    )

    id = db.Column(db.Integer, primary_key=True)
    equipe_id = db.Column(db.Integer, db.ForeignKey("equipes.id", ondelete="CASCADE"), nullable=False)
    membro_id = db.Column(db.Integer, db.ForeignKey("members.id", ondelete="CASCADE"), nullable=False)
    funcao_padrao_id = db.Column(db.Integer, db.ForeignKey("equipe_funcoes.id", ondelete="SET NULL"), nullable=True)

    ativo = db.Column(db.Boolean, default=True)
    data_ingresso = db.Column(db.Date, default=date.today)

    # Relacionamentos
    membro = db.relationship("Member", backref="participacoes_equipe")
    funcao_padrao = db.relationship("EquipeFuncao", foreign_keys=[funcao_padrao_id])

    def __repr__(self):
        return f"<EquipeMembro {self.membro.nome if self.membro else self.membro_id} na equipe {self.equipe_id}>"


# ---------------------------------------------------------------------------
# 📅 Escala de Atividades / Culto
# ---------------------------------------------------------------------------
class Escala(db.Model):
    __tablename__ = "escalas"

    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(150), nullable=False)  # Ex: "Culto de Celebração & Santa Ceia"
    data = db.Column(db.Date, nullable=False)
    hora_inicio = db.Column(db.String(10), nullable=False, default="18:00")
    hora_fim = db.Column(db.String(10), nullable=True, default="20:30")

    # Vínculo opcional com evento/culto do calendário oficial
    evento_id = db.Column(db.Integer, db.ForeignKey("eventos.id", ondelete="SET NULL"), nullable=True)
    evento = db.relationship("Evento", backref="escalas")

    local = db.Column(db.String(150), nullable=True, default="Templo Principal")
    observacoes = db.Column(db.Text, nullable=True)

    # Status: rascunho, publicada, confirmada, concluida, cancelada
    status = db.Column(db.String(20), nullable=False, default="rascunho")

    # Token para visualização pública e confirmação sem login pelos voluntários
    public_token = db.Column(
        db.String(32),
        unique=True,
        nullable=False,
        default=lambda: secrets.token_urlsafe(16)
    )

    criado_por_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    criado_por = db.relationship("User", foreign_keys=[criado_por_id])

    criado_em = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    atualizado_em = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # Itens (Pessoas escaladas)
    itens = db.relationship(
        "EscalaItem",
        back_populates="escala",
        cascade="all, delete-orphan",
        order_by="EscalaItem.id.asc()",
        lazy=True
    )

    @property
    def total_escalados(self):
        return len(self.itens)

    @property
    def total_confirmados(self):
        return len([i for i in self.itens if i.status == "confirmado"])

    @property
    def total_pendentes(self):
        return len([i for i in self.itens if i.status == "pendente"])

    @property
    def total_recusados(self):
        return len([i for i in self.itens if i.status == "recusado"])

    @property
    def status_badge_class(self):
        badges = {
            "rascunho": "bg-secondary",
            "publicada": "bg-primary",
            "confirmada": "bg-success",
            "concluida": "bg-info text-dark",
            "cancelada": "bg-danger",
        }
        return badges.get(self.status, "bg-secondary")

    @property
    def status_display(self):
        nomes = {
            "rascunho": "Rascunho",
            "publicada": "Publicada",
            "confirmada": "Confirmada",
            "concluida": "Concluída",
            "cancelada": "Cancelada",
        }
        return nomes.get(self.status, self.status.capitalize())

    def __repr__(self):
        return f"<Escala {self.titulo} ({self.data} {self.hora_inicio})>"


# ---------------------------------------------------------------------------
# 🙋‍♂️ Item da Escala (Voluntário Escalado)
# ---------------------------------------------------------------------------
class EscalaItem(db.Model):
    __tablename__ = "escala_itens"

    id = db.Column(db.Integer, primary_key=True)
    escala_id = db.Column(db.Integer, db.ForeignKey("escalas.id", ondelete="CASCADE"), nullable=False)
    equipe_id = db.Column(db.Integer, db.ForeignKey("equipes.id", ondelete="CASCADE"), nullable=False)
    funcao_id = db.Column(db.Integer, db.ForeignKey("equipe_funcoes.id", ondelete="SET NULL"), nullable=True)
    membro_id = db.Column(db.Integer, db.ForeignKey("members.id", ondelete="CASCADE"), nullable=False)

    # Status: pendente, confirmado, recusado, substituido
    status = db.Column(db.String(30), nullable=False, default="pendente")
    observacao = db.Column(db.String(255), nullable=True)
    confirmado_em = db.Column(db.DateTime, nullable=True)

    # Histórico de Substituição (Preserva voluntário original)
    membro_original_id = db.Column(db.Integer, db.ForeignKey("members.id", ondelete="SET NULL"), nullable=True)
    motivo_substituicao = db.Column(db.String(255), nullable=True)
    substituido_em = db.Column(db.DateTime, nullable=True)
    substituido_por_usuario_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    criado_em = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relacionamentos
    escala = db.relationship("Escala", back_populates="itens")
    equipe = db.relationship("Equipe", back_populates="itens_escala")
    funcao = db.relationship("EquipeFuncao", foreign_keys=[funcao_id])
    membro = db.relationship("Member", foreign_keys=[membro_id], backref="escalas_participadas")
    membro_original = db.relationship("Member", foreign_keys=[membro_original_id], backref="escalas_substituidas")
    substituido_por_usuario = db.relationship("User", foreign_keys=[substituido_por_usuario_id])

    @property
    def status_badge_class(self):
        badges = {
            "pendente": "bg-warning text-dark",
            "confirmado": "bg-success",
            "recusado": "bg-danger",
            "substituido": "bg-info text-dark",
        }
        return badges.get(self.status, "bg-secondary")

    @property
    def status_display(self):
        nomes = {
            "pendente": "Pendente",
            "confirmado": "Confirmado",
            "recusado": "Recusado",
            "substituido": "Substituído",
        }
        return nomes.get(self.status, self.status.capitalize())

    def __repr__(self):
        membro_nome = self.membro.nome if self.membro else self.membro_id
        return f"<EscalaItem {membro_nome} - {self.status}>"
