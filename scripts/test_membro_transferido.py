#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
🧪 SiGI — Suíte de Testes Automatizados: Status TRANSFERIDO e Contabilização de Membros
Validação completa dos 6 cenários de negócio estabelecidos para transferência e contabilização.
"""

import sys
import os
from pathlib import Path
from datetime import date, datetime

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from app import create_app, db
from app.models import Member, User, PublicLink
from app.services.dashboard_service import DashboardService

app = create_app()
app.config["TESTING"] = True
app.config["WTF_CSRF_ENABLED"] = False

def run_tests():
    print("\n" + "=" * 75)
    print("  🧪 SUÍTE DE TESTES: STATUS 'TRANSFERIDO' & CONTABILIZAÇÃO DE MEMBROS (SiGI)")
    print("=" * 75 + "\n")

    with app.test_client() as client:
        with app.app_context():
            db.create_all()

            # Cria Administrador para testes autenticados
            admin = User.query.filter_by(email="admin_transfer_test@sigi.com").first()
            if not admin:
                admin = User(
                    nome="Admin Transfer Test",
                    email="admin_transfer_test@sigi.com",
                    is_admin=True,
                    ativo=True
                )
                admin.set_password("Admin@123456")
                db.session.add(admin)
                db.session.commit()

            # Autentica na sessão de teste
            with client.session_transaction() as sess:
                sess['_user_id'] = str(admin.id)
                sess['_fresh'] = True

            # Limpa dados de testes anteriores com emails de teste
            Member.query.filter(Member.email.ilike("%@testtransfer.com")).delete(synchronize_session=False)
            db.session.commit()

            # -------------------------------------------------------------
            # CENÁRIO 1 — Membro Ativo
            # -------------------------------------------------------------
            print("▶ [Cenário 1] Membro com status ATIVO deve ser contabilizado como ativo...")
            membro_ativo_1 = Member(
                nome="João Silva Ativo",
                email="joao.ativo@testtransfer.com",
                status="Ativo",
                funcao="Membro",
                data_cadastro=date.today(),
                data_nascimento=date(1990, 5, 15),
                telefone="(11) 98888-0001"
            )
            db.session.add(membro_ativo_1)
            db.session.commit()

            assert membro_ativo_1.ativo is True, "Propriedade membro.ativo deve ser True para status Ativo"
            print("  ✅ [OK] Membro ativo validado com sucesso (ativo=True).")

            # -------------------------------------------------------------
            # CENÁRIO 2 — Transferência de Membro
            # -------------------------------------------------------------
            print("\n▶ [Cenário 2] Alterar status para TRANSFERIDO, preservar cadastro e retirar de ativos...")
            membro_transferir = Member(
                nome="Maria Souza Transferida",
                email="maria.transfer@testtransfer.com",
                status="Ativo",
                funcao="Diácono",
                data_cadastro=date(2020, 1, 10),
                data_nascimento=date(1985, 3, 20),
                observacoes="<p>Membro solicitou transferência para congregação filial.</p>"
            )
            db.session.add(membro_transferir)
            db.session.commit()
            membro_id = membro_transferir.id

            # Simula alteração do status para Transferido via HTTP POST no formulário de edição
            res_post = client.post(f"/membros/editar/{membro_id}", data={
                "nome": "Maria Souza Transferida",
                "status": "Transferido",
                "funcao": "Diácono",
                "observacoes": "<p>Membro solicitou transferência para congregação filial.</p>"
            }, follow_redirects=True)
            assert res_post.status_code == 200, "Edição via HTTP POST deve responder com HTTP 200 (redirecionamento com sucesso)"

            # Recarrega do banco
            membro_recarregado = db.session.get(Member, membro_id)
            assert membro_recarregado is not None, "O cadastro do membro deve permanecer salvo no banco de dados"
            assert membro_recarregado.status == "Transferido", "O status deve ser atualizado para 'Transferido'"
            assert membro_recarregado.ativo is False, "A propriedade ativo deve retornar False para membro Transferido"
            assert "solicitou transferência" in (membro_recarregado.observacoes or ""), "Observações e histórico devem ser preservados"
            print("  ✅ [OK] Membro transferido via formulário com sucesso. Cadastro preservado e retirado dos ativos.")

            # -------------------------------------------------------------
            # CENÁRIO 3 — Contagem Quantitativa
            # -------------------------------------------------------------
            print("\n▶ [Cenário 3] Contagem: 10 membros ATIVO + 2 membros TRANSFERIDO...")
            # Cria 9 membros ativos adicionais (totalizando 10 ativos com o membro_ativo_1)
            membros_ativos_lote = []
            for i in range(2, 11):
                membros_ativos_lote.append(
                    Member(
                        nome=f"Membro Ativo {i}",
                        email=f"ativo_{i}@testtransfer.com",
                        status="Ativo",
                        funcao="Membro",
                        data_cadastro=date.today(),
                        data_nascimento=date(1992, 1, i)
                    )
                )
            # Cria 1 membro transferido adicional (totalizando 2 com Maria Souza)
            membro_transf_2 = Member(
                nome="Pedro Santos Transferido",
                email="pedro.transfer@testtransfer.com",
                status="Transferido",
                funcao="Membro",
                data_cadastro=date(2021, 6, 1)
            )
            db.session.add_all(membros_ativos_lote + [membro_transf_2])
            db.session.commit()

            total_ativos_teste = Member.query.filter(
                Member.email.ilike("%@testtransfer.com"),
                (Member.status == "Ativo") & (Member.data_saida.is_(None))
            ).count()

            total_geral_teste = Member.query.filter(
                Member.email.ilike("%@testtransfer.com")
            ).count()

            assert total_ativos_teste == 10, f"Esperado 10 membros ativos, obtido: {total_ativos_teste}"
            assert total_geral_teste == 12, f"Esperado 12 membros no total geral cadastrado, obtido: {total_geral_teste}"
            print(f"  ✅ [OK] Total geral: {total_geral_teste} | Total ativos: {total_ativos_teste} (10 ativos e 2 transferidos).")

            # -------------------------------------------------------------
            # CENÁRIO 4 — Listagem Padrão de Membros
            # -------------------------------------------------------------
            print("\n▶ [Cenário 4] Listagem padrão de membros (status=Ativo) não deve conter TRANSFERIDO...")
            resp_padrao = client.get("/membros/?q=transfer")
            assert resp_padrao.status_code == 200
            conteudo_padrao = resp_padrao.get_data(as_text=True)

            assert "Maria Souza Transferida" not in conteudo_padrao, "Membro Transferido não deve constar na listagem padrão"
            assert "Pedro Santos Transferido" not in conteudo_padrao, "Membro Transferido não deve constar na listagem padrão"
            print("  ✅ [OK] Listagem padrão omite corretamente membros Transferidos.")

            # -------------------------------------------------------------
            # CENÁRIO 5 — Consulta Histórica e Filtro
            # -------------------------------------------------------------
            print("\n▶ [Cenário 5] Filtro por status=Transferido deve localizar membros transferidos...")
            resp_transf = client.get("/membros/?status=Transferido&q=transfer")
            assert resp_transf.status_code == 200
            conteudo_transf = resp_transf.get_data(as_text=True)

            assert "Maria Souza Transferida" in conteudo_transf, "Membro Transferido deve aparecer no filtro Transferido"
            assert "Pedro Santos Transferido" in conteudo_transf, "Membro Transferido deve aparecer no filtro Transferido"
            assert "Transferido" in conteudo_transf, "Badge de Transferido deve ser exibido"
            print("  ✅ [OK] Membros transferidos localizados com sucesso no filtro de histórico.")

            # -------------------------------------------------------------
            # CENÁRIO 6 — Dashboard e Indicadores
            # -------------------------------------------------------------
            print("\n▶ [Cenário 6] Dashboard: métricas devem considerar somente membros ativos...")
            metrics_antes = DashboardService.get_dashboard_metrics(is_admin=True)
            total_membros_antes = metrics_antes["total_membros"]

            # Transfere mais um membro ativo
            membro_a_transferir = Member.query.filter_by(email="ativo_2@testtransfer.com").first()
            assert membro_a_transferir is not None
            membro_a_transferir.status = "Transferido"
            db.session.commit()

            metrics_depois = DashboardService.get_dashboard_metrics(is_admin=True)
            total_membros_depois = metrics_depois["total_membros"]

            assert total_membros_depois == total_membros_antes - 1, (
                f"Dashboard deveria decrementar de {total_membros_antes} para {total_membros_antes - 1}, "
                f"mas obteve {total_membros_depois}"
            )
            print(f"  ✅ [OK] Total no Dashboard antes: {total_membros_antes} -> depois: {total_membros_depois} (decremento correto).")

            # Limpeza final dos registros de teste
            Member.query.filter(Member.email.ilike("%@testtransfer.com")).delete(synchronize_session=False)
            db.session.commit()

    print("\n" + "=" * 75)
    print("  🎉 TODOS OS 6 CENÁRIOS FORAM VALIDADOS COM 100% DE SUCESSO!")
    print("=" * 75 + "\n")

if __name__ == "__main__":
    run_tests()
