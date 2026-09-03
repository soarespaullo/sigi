import sys
import os
from datetime import date, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from app import create_app, db
from app.models import Member, User, Evento, Equipe, EquipeFuncao, EquipeMembro, Escala, EscalaItem
from app.services.escala_service import EscalaService

app = create_app()

def seed_escalas():
    with app.app_context():
        print("=" * 60)
        print("SEED: Módulo de Escalas e Voluntários")
        print("=" * 60)

        # Se já existirem equipes, não duplica
        if Equipe.query.count() > 0:
            print("[INFO] Equipes já cadastradas. Pulando seed inicial.")
            return

        membros = Member.query.filter((Member.status.is_(None)) | (Member.status == "Ativo")).all()
        if not membros:
            print("[AVISO] Nenhum membro encontrado para popular equipes.")
            return

        admin = User.query.filter_by(is_admin=True).first()

        # 1. Equipe: Louvor & Adoração
        louvor = Equipe(
            nome="Ministério de Louvor",
            descricao="Condução da adoração musical congregacional durante os cultos e celebrações.",
            cor="#8b5cf6",
            icone="bi-music-note-beamed",
            lider_id=membros[0].id if len(membros) > 0 else None,
            ativo=True
        )
        db.session.add(louvor)
        db.session.flush()

        funcoes_louvor = [
            EquipeFuncao(equipe_id=louvor.id, nome="Vocal Principal / Dirigente", ordem=1),
            EquipeFuncao(equipe_id=louvor.id, nome="Backing Vocal", ordem=2),
            EquipeFuncao(equipe_id=louvor.id, nome="Violão Acústico", ordem=3),
            EquipeFuncao(equipe_id=louvor.id, nome="Teclado / Piano", ordem=4),
            EquipeFuncao(equipe_id=louvor.id, nome="Bateria", ordem=5),
            EquipeFuncao(equipe_id=louvor.id, nome="Contrabaixo", ordem=6),
        ]
        db.session.add_all(funcoes_louvor)

        # 2. Equipe: Recepção & Boas-Vindas
        recepcao = Equipe(
            nome="Recepção & Boas-Vindas",
            descricao="Acolhimento aos membros e visitantes na entrada do templo, entrega de boletins e orientações.",
            cor="#0ea5e9",
            icone="bi-door-open",
            lider_id=membros[1].id if len(membros) > 1 else None,
            ativo=True
        )
        db.session.add(recepcao)
        db.session.flush()

        funcoes_recepcao = [
            EquipeFuncao(equipe_id=recepcao.id, nome="Recepcionista Entrada Principal", ordem=1),
            EquipeFuncao(equipe_id=recepcao.id, nome="Acolhimento de Visitantes", ordem=2),
            EquipeFuncao(equipe_id=recepcao.id, nome="Apoio no Nave do Templo", ordem=3),
        ]
        db.session.add_all(funcoes_recepcao)

        # 3. Equipe: Mídia & Sonoplastia
        midia = Equipe(
            nome="Mídia & Sonoplastia",
            descricao="Operação da mesa de som, transmissão ao vivo, projeção de letras e iluminação do templo.",
            cor="#f59e0b",
            icone="bi-camera-video",
            lider_id=membros[2].id if len(membros) > 2 else None,
            ativo=True
        )
        db.session.add(midia)
        db.session.flush()

        funcoes_midia = [
            EquipeFuncao(equipe_id=midia.id, nome="Operador de Mesa de Som", ordem=1),
            EquipeFuncao(equipe_id=midia.id, nome="Projeção / Telão", ordem=2),
            EquipeFuncao(equipe_id=midia.id, nome="Transmissão ao Vivo (Câmera)", ordem=3),
            EquipeFuncao(equipe_id=midia.id, nome="Fotografia / Redes Sociais", ordem=4),
        ]
        db.session.add_all(funcoes_midia)

        # 4. Equipe: Diaconia & Apoio
        diaconia = Equipe(
            nome="Diaconia & Ordem",
            descricao="Assistência ao altar, recolhimento de dízimos/ofertas, suporte na Santa Ceia e apoio geral.",
            cor="#10b981",
            icone="bi-shield-check",
            lider_id=membros[3].id if len(membros) > 3 else None,
            ativo=True
        )
        db.session.add(diaconia)
        db.session.flush()

        funcoes_diaconia = [
            EquipeFuncao(equipe_id=diaconia.id, nome="Diácono da Santa Ceia", ordem=1),
            EquipeFuncao(equipe_id=diaconia.id, nome="Coleta de Dízimos e Ofertas", ordem=2),
            EquipeFuncao(equipe_id=diaconia.id, nome="Apoio ao Púlpito", ordem=3),
        ]
        db.session.add_all(funcoes_diaconia)
        db.session.commit()

        # Vincula alguns membros às equipes
        idx = 0
        for eq in [louvor, recepcao, midia, diaconia]:
            for _ in range(4):
                if idx < len(membros):
                    m = membros[idx]
                    f_padrao = eq.funcoes[0] if eq.funcoes else None
                    vm = EquipeMembro(equipe_id=eq.id, membro_id=m.id, funcao_padrao_id=f_padrao.id if f_padrao else None)
                    db.session.add(vm)
                    idx += 1
        db.session.commit()
        print("[OK] Equipes, Funções e Voluntários associados com sucesso.")

        # Cria uma escala de exemplo para o próximo domingo
        hoje = date.today()
        dias_ate_domingo = (6 - hoje.weekday()) % 7
        if dias_ate_domingo == 0:
            dias_ate_domingo = 7
        proximo_domingo = hoje + timedelta(days=dias_ate_domingo)

        evento_domingo = Evento.query.filter(Evento.data_inicio >= hoje).first()

        escala_exemplo = Escala(
            titulo="Culto de Celebração — Domingo Noite",
            data=proximo_domingo,
            hora_inicio="18:00",
            hora_fim="20:15",
            evento_id=evento_domingo.id if evento_domingo else None,
            local="Templo Principal",
            observacoes="Por favor, chegar às 17h30 para momento de oração e alinhamento das equipes.",
            status="publicada",
            criado_por_id=admin.id if admin else None
        )
        db.session.add(escala_exemplo)
        db.session.flush()

        # Escalar pessoas para o culto
        itens = [
            EscalaItem(escala_id=escala_exemplo.id, equipe_id=louvor.id, funcao_id=funcoes_louvor[0].id, membro_id=membros[0].id, status="confirmado"),
            EscalaItem(escala_id=escala_exemplo.id, equipe_id=louvor.id, funcao_id=funcoes_louvor[3].id, membro_id=membros[1].id, status="confirmado"),
            EscalaItem(escala_id=escala_exemplo.id, equipe_id=recepcao.id, funcao_id=funcoes_recepcao[0].id, membro_id=membros[4].id, status="pendente"),
            EscalaItem(escala_id=escala_exemplo.id, equipe_id=recepcao.id, funcao_id=funcoes_recepcao[1].id, membro_id=membros[5].id, status="confirmado"),
            EscalaItem(escala_id=escala_exemplo.id, equipe_id=midia.id, funcao_id=funcoes_midia[0].id, membro_id=membros[8].id, status="confirmado"),
            EscalaItem(escala_id=escala_exemplo.id, equipe_id=midia.id, funcao_id=funcoes_midia[1].id, membro_id=membros[9].id, status="pendente"),
            EscalaItem(escala_id=escala_exemplo.id, equipe_id=diaconia.id, funcao_id=funcoes_diaconia[1].id, membro_id=membros[12].id, status="confirmado"),
        ]
        db.session.add_all(itens)
        db.session.commit()

        print(f"[OK] Escala de demonstração criada: '{escala_exemplo.titulo}' para {proximo_domingo.strftime('%d/%m/%Y')} com {len(itens)} voluntários escalados.")

if __name__ == "__main__":
    seed_escalas()
