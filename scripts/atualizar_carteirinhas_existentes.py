import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from datetime import date, timedelta
from app import create_app
from app.extensions import db
from app.models.member import Member
from app.routes.member.member import calcular_validade_carteira

app = create_app()

with app.app_context():
    print("Iniciando migracao retroativa de carteirinhas de membros...")
    
    # Busca todos os membros ordenados por data de cadastro e ID
    membros = Member.query.order_by(Member.data_cadastro.asc(), Member.id.asc()).all()
    print(f"Total de membros encontrados: {len(membros)}")
    
    seq = 1
    atualizados = 0
    for m in membros:
        numero = f"{seq:05d}"
        dt_base = m.data_cadastro or date.today()
        val = calcular_validade_carteira(dt_base)
        
        m.numero_carteira = numero
        m.validade = val
        seq += 1
        atualizados += 1
        print(f"Membro #{m.id} - {m.nome} -> Carteira: {m.numero_carteira} | Validade: {m.validade.strftime('%d/%m/%Y')}")
    
    db.session.commit()
    print(f"[SUCESSO] {atualizados} membros atualizados com carteirinhas de 00001 ate {seq-1:05d} e validade fixa de 365 dias!")
