import unittest
import os
import sys
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import User, Member
from app.models.patrimonio import Patrimonio
from app.models.evento import Evento
from datetime import datetime, timedelta

class TestAutocompleteSystem(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()

        with self.app.app_context():
            user = User.query.filter_by(is_admin=True).first()
            if not user:
                user = User(
                    nome="Admin Teste",
                    email="admin_auto@sigi.local",
                    is_admin=True
                )
                user.set_password("admin123")
                db.session.add(user)
                db.session.commit()
            self.user_id = user.id

            # Garante dados de teste para busca
            membro_teste1 = Member.query.filter_by(nome="João da Silva").first()
            if not membro_teste1:
                membro_teste1 = Member(
                    nome="João da Silva",
                    email="joao.silva@teste.com",
                    funcao="Diácono",
                    status="Ativo"
                )
                db.session.add(membro_teste1)

            membro_teste2 = Member.query.filter_by(nome="Maria Antônia dos Santos").first()
            if not membro_teste2:
                membro_teste2 = Member(
                    nome="Maria Antônia dos Santos",
                    email="maria.santos@teste.com",
                    funcao="Líder EBD",
                    status="Ativo"
                )
                db.session.add(membro_teste2)

            membro_teste3 = Member.query.filter_by(nome="Marcos Pereira").first()
            if not membro_teste3:
                membro_teste3 = Member(
                    nome="Marcos Pereira",
                    email="marcos.pereira@teste.com",
                    funcao="Músico",
                    status="Ativo"
                )
                db.session.add(membro_teste3)

            db.session.commit()

    def login(self):
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(self.user_id)
            sess['_fresh'] = True

    def test_unauthenticated_access_blocked(self):
        """Verifica se acesso sem login é bloqueado no endpoint de autocomplete"""
        response = self.client.get("/api/busca/membros?q=Mar")
        self.assertIn(response.status_code, [302, 401])

    def test_busca_membros_prefixo_mar(self):
        """Testa busca por prefixo 'Mar' retornando membros esperados e NÃO trazendo pessoas cujo nome não começa com Mar (ex: Beatriz Martins, Isabela Guimarães)"""
        with self.app.app_context():
            # Garante membro com Martins no sobrenome para teste negativo
            bia = Member.query.filter_by(nome="Beatriz Martins Oliveira").first()
            if not bia:
                bia = Member(nome="Beatriz Martins Oliveira", status="Ativo", funcao="Líder de Louvor")
                db.session.add(bia)
                db.session.commit()

            self.login()
            response = self.client.get("/api/busca/membros?q=Mar")
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.get_data(as_text=True))
            self.assertIsInstance(data, list)
            self.assertTrue(len(data) >= 1)
            self.assertLessEqual(len(data), 10) # Limite padrão de 10 resultados

            nomes = [item['label'] for item in data]
            print("[OK] Resultados retornados para 'Mar':", nomes)

            # TODOS os nomes retornados devem começar com 'Mar' (case-insensitive)
            for nome in nomes:
                self.assertTrue(nome.lower().startswith("mar"), f"Nome '{nome}' não começa com 'Mar'!")

            # Verifica explicitamente que Beatriz Martins e Isabela Guimarães NÃO estão presentes
            self.assertFalse(any("Beatriz" in nome for nome in nomes), "Beatriz Martins não deveria aparecer ao buscar 'Mar'!")
            self.assertFalse(any("Isabela" in nome for nome in nomes), "Isabela Guimarães não deveria aparecer ao buscar 'Mar'!")

    def test_busca_membros_tolerante_a_acentos(self):
        """Testa busca sem acento 'joao' encontrando 'João da Silva'"""
        with self.app.app_context():
            self.login()
            response = self.client.get("/api/busca/membros?q=joao")
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.get_data(as_text=True))
            nomes = [item['label'] for item in data]
            self.assertTrue(any("João" in nome or "Joao" in nome for nome in nomes))
            print("[OK] Busca sem acento 'joao' encontrou 'João da Silva':", nomes)

    def test_busca_min_chars_and_empty(self):
        """Testa que buscas com menos de 2 caracteres retornam lista vazia"""
        with self.app.app_context():
            self.login()
            response = self.client.get("/api/busca/membros?q=M")
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.get_data(as_text=True))
            self.assertEqual(data, [])

            response_vazio = self.client.get("/api/busca/membros?q=xyzinexistente999")
            self.assertEqual(response_vazio.status_code, 200)
            data_vazio = json.loads(response_vazio.get_data(as_text=True))
            self.assertEqual(data_vazio, [])
            print("[OK] Validado comportamento de busca vazia e caracteres mínimos.")

    def test_busca_patrimonios_and_eventos(self):
        """Testa endpoints de patrimônios e eventos"""
        with self.app.app_context():
            self.login()
            resp_pat = self.client.get("/api/busca/patrimonios?q=som")
            self.assertEqual(resp_pat.status_code, 200)
            self.assertIsInstance(json.loads(resp_pat.get_data(as_text=True)), list)

            resp_ev = self.client.get("/api/busca/eventos?q=culto")
            self.assertEqual(resp_ev.status_code, 200)
            self.assertIsInstance(json.loads(resp_ev.get_data(as_text=True)), list)
            print("[OK] Endpoints de patrimonios e eventos respondendo com 200 OK.")

    def test_busca_financeiro_entradas_e_saidas(self):
        """Testa endpoints de autocomplete de receitas e despesas financeiras"""
        with self.app.app_context():
            self.login()
            resp_ent = self.client.get("/api/busca/entradas?q=Diz")
            self.assertEqual(resp_ent.status_code, 200)
            self.assertIsInstance(json.loads(resp_ent.get_data(as_text=True)), list)

            # Testar busca de membro pelo nome em entradas (ex: Pris)
            resp_membro_ent = self.client.get("/api/busca/entradas?q=Pris")
            self.assertEqual(resp_membro_ent.status_code, 200)
            dados = json.loads(resp_membro_ent.get_data(as_text=True))
            self.assertIsInstance(dados, list)
            if dados:
                # O label deve ser o nome da pessoa e a inicial 'P'
                self.assertTrue(any(d["label"].startswith("Pris") and d["inicial"] == "P" for d in dados))

            resp_sai = self.client.get("/api/busca/saidas?q=Con")
            self.assertEqual(resp_sai.status_code, 200)
            self.assertIsInstance(json.loads(resp_sai.get_data(as_text=True)), list)
            print("[OK] Endpoints de busca de entradas e saidas com identificação de membro respondendo com 200 OK.")

if __name__ == "__main__":
    unittest.main()
