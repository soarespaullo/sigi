import secrets
from datetime import datetime, timezone, date
from sqlalchemy import or_, and_, func, extract

from app.extensions import db
from app.models import Escala, EscalaItem, Equipe, EquipeFuncao, EquipeMembro, Member, User
from utils.logs import registrar_log


class EscalaService:
    """
    Serviço corporativo para regras de negócio de Escalas:
    - Detecção inteligente de conflitos de horários e duplicidades
    - Balanceamento de voluntários (frequência mensal)
    - Duplicação segura de escalas
    - Substituição com preservação de histórico auditável
    """

    @staticmethod
    def parse_minutos(hora_str: str) -> int:
        """Converte 'HH:MM' em minutos a partir da meia-noite para comparação numérica precisa."""
        if not hora_str:
            return 0
        try:
            partes = hora_str.strip().split(":")
            return int(partes[0]) * 60 + int(partes[1])
        except (ValueError, IndexError):
            return 0

    @classmethod
    def verificar_conflitos(cls, membro_id: int, escala_data: date, hora_inicio: str, hora_fim: str = None, escala_id: int = None):
        """
        Analisa conflitos potenciais para um voluntário:
        1. Se já está escalado no mesmo horário em outra atividade (conflito grave)
        2. Se já está escalado na mesma escala (dupla função - aviso)
        3. Contagem de escalas no mesmo mês (balanceamento / sobrecarga)
        """
        conflitos = []
        avisos = []

        membro = db.session.get(Member, membro_id)
        if not membro:
            return {
                "possui_conflito": True,
                "conflitos": ["Voluntário não encontrado."],
                "avisos": [],
                "escalas_no_mes": 0
            }

        inicio_min = cls.parse_minutos(hora_inicio)
        fim_min = cls.parse_minutos(hora_fim) if hora_fim else (inicio_min + 120)  # Padrão: 2 horas de duração

        # 1. Checa itens em escalas no mesmo dia
        itens_no_mesmo_dia = (
            EscalaItem.query
            .join(Escala)
            .filter(
                EscalaItem.membro_id == membro_id,
                Escala.data == escala_data,
                Escala.status != "cancelada",
                EscalaItem.status != "recusado"
            )
            .all()
        )

        for item in itens_no_mesmo_dia:
            if escala_id and item.escala_id == escala_id:
                funcao_nome = item.funcao.nome if item.funcao else "Função Geral"
                equipe_nome = item.equipe.nome if item.equipe else "Equipe"
                avisos.append(
                    f"{membro.nome} já possui atribuição nesta mesma escala: {equipe_nome} ({funcao_nome})."
                )
            else:
                # Checa sobreposição de horários
                outra_escala = item.escala
                outra_inicio_min = cls.parse_minutos(outra_escala.hora_inicio)
                outra_fim_min = cls.parse_minutos(outra_escala.hora_fim) if outra_escala.hora_fim else (outra_inicio_min + 120)

                # Interseção de intervalos: max(inicio1, inicio2) < min(fim1, fim2)
                if max(inicio_min, outra_inicio_min) < min(fim_min, outra_fim_min):
                    conflitos.append(
                        f"Choque de horário com a escala '{outra_escala.titulo}' "
                        f"({outra_escala.hora_inicio} às {outra_escala.hora_fim or '?'}) na equipe {item.equipe.nome}."
                    )

        # 2. Contagem mensal de participações para balancear equipe
        ano = escala_data.year
        mes = escala_data.month
        total_no_mes = (
            EscalaItem.query
            .join(Escala)
            .filter(
                EscalaItem.membro_id == membro_id,
                extract("year", Escala.data) == ano,
                extract("month", Escala.data) == mes,
                Escala.status != "cancelada",
                EscalaItem.status != "recusado"
            )
            .count()
        )

        if total_no_mes >= 4:
            avisos.append(
                f"Atenção: {membro.nome} já foi escalado(a) {total_no_mes} vezes neste mês. Considere revezar voluntários."
            )

        return {
            "possui_conflito": len(conflitos) > 0,
            "conflitos": conflitos,
            "avisos": avisos,
            "escalas_no_mes": total_no_mes,
            "membro_nome": membro.nome
        }

    @classmethod
    def duplicar_escala(cls, escala_id: int, nova_data: date, nova_hora_inicio: str = None, nova_hora_fim: str = None, novo_titulo: str = None, usuario: User = None) -> Escala:
        """
        Clona integralmente a estrutura de uma escala para uma nova data:
        - Equipes e funções preservadas
        - Pessoas escaladas mantidas
        - Status resetado para 'rascunho' e 'pendente'
        - Novo token público seguro gerado
        """
        original = Escala.query.get_or_404(escala_id)

        titulo = novo_titulo.strip() if novo_titulo else f"{original.titulo} (Cópia)"
        hora_inicio = nova_hora_inicio.strip() if nova_hora_inicio else original.hora_inicio
        hora_fim = nova_hora_fim.strip() if nova_hora_fim else original.hora_fim

        nova_escala = Escala(
            titulo=titulo,
            data=nova_data,
            hora_inicio=hora_inicio,
            hora_fim=hora_fim,
            evento_id=None,  # Não herda evento original para evitar duplicar vínculo
            local=original.local,
            observacoes=original.observacoes,
            status="rascunho",
            public_token=secrets.token_urlsafe(16),
            criado_por_id=usuario.id if usuario else None
        )

        db.session.add(nova_escala)
        db.session.flush()  # Obtém o ID da nova escala

        for item_orig in original.itens:
            novo_item = EscalaItem(
                escala_id=nova_escala.id,
                equipe_id=item_orig.equipe_id,
                funcao_id=item_orig.funcao_id,
                membro_id=item_orig.membro_id,
                status="pendente",
                observacao=item_orig.observacao,
                confirmado_em=None,
                membro_original_id=None,
                motivo_substituicao=None,
                substituido_em=None,
                substituido_por_usuario_id=None
            )
            db.session.add(novo_item)

        db.session.commit()

        if usuario:
            registrar_log(usuario.nome, f"Duplicou escala '{original.titulo}' para '{nova_escala.titulo}' em {nova_data.strftime('%d/%m/%Y')}", "sucesso")

        return nova_escala

    @classmethod
    def substituir_voluntario(cls, item_id: int, novo_membro_id: int, motivo: str, usuario: User = None) -> EscalaItem:
        """
        Efetua a substituição de um voluntário preservando o histórico integral:
        - Mantém quem era o membro original
        - Registra timestamp e motivo da troca
        - Atualiza status para 'substituido'
        """
        item = EscalaItem.query.get_or_404(item_id)
        novo_membro = Member.query.get_or_404(novo_membro_id)

        # Se nunca foi substituído, o original é o membro atual
        if not item.membro_original_id:
            item.membro_original_id = item.membro_id

        membro_anterior_nome = item.membro.nome if item.membro else f"Membro #{item.membro_id}"

        item.membro_id = novo_membro.id
        item.motivo_substituicao = motivo.strip() if motivo else "Substituição solicitada"
        item.substituido_em = datetime.now(timezone.utc)
        item.substituido_por_usuario_id = usuario.id if usuario else None
        item.status = "substituido"

        db.session.commit()

        if usuario:
            registrar_log(
                usuario.nome,
                f"Substituiu {membro_anterior_nome} por {novo_membro.nome} na escala '{item.escala.titulo}' (Motivo: {item.motivo_substituicao})",
                "sucesso"
            )

        return item
