#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
🧪 Suíte de Testes Automatizados — Integração Global de CEP com ViaCEP no SiGI
Testa o endpoint de backend (/api/cep/<cep>), a validação de formato,
o retorno da API externa, o tratamento de erros e a presença do componente
nos formulários de Membros, Visitantes e Igreja.
"""

import os
import sys
import json
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app, db
from app.models import User, Member, PublicLink, Igreja

class TestViaCepIntegration(unittest.TestCase):

    def setUp(self):
        self.app = create_app()
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.app.config['TESTING'] = True
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()

        # Garante usuário administrador para autenticação
        self.admin = User.query.filter_by(email="admin_viacep@sigi.local").first()
        if not self.admin:
            self.admin = User(
                nome="Admin ViaCEP",
                email="admin_viacep@sigi.local",
                is_admin=True,
                ativo=True
            )
            self.admin.set_password("Senha123!")
            db.session.add(self.admin)
            db.session.commit()

        # Garante membro para teste de edição
        self.membro = Member.query.filter_by(email="membro_viacep@sigi.local").first()
        if not self.membro:
            self.membro = Member(
                nome="Membro Teste ViaCEP",
                email="membro_viacep@sigi.local",
                status="Ativo"
            )
            db.session.add(self.membro)
            db.session.commit()

        # Realiza login
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(self.admin.id)
            sess['_fresh'] = True

    def tearDown(self):
        self.app_context.pop()

    def test_endpoint_cep_valido_com_mascara(self):
        """Testa consulta com CEP formatado '01001-000' (Praça da Sé)"""
        resp = self.client.get("/api/cep/01001-000")
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.get_data(as_text=True))
        self.assertTrue(data.get("success"))
        self.assertIn("Praça da Sé", data.get("logradouro"))
        self.assertEqual(data.get("bairro"), "Sé")
        self.assertEqual(data.get("cidade"), "São Paulo")
        self.assertEqual(data.get("uf"), "SP")
        print("[OK] Endpoint /api/cep/01001-000 retornou dados corretos.")

    def test_endpoint_cep_valido_sem_mascara(self):
        """Testa consulta com CEP apenas dígitos '01001000'"""
        resp = self.client.get("/api/cep/01001000")
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.get_data(as_text=True))
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("cidade"), "São Paulo")
        print("[OK] Endpoint /api/cep/01001000 sem máscara normalizado e respondido.")

    def test_endpoint_cep_incompleto(self):
        """Testa CEP incompleto com menos de 8 dígitos"""
        resp = self.client.get("/api/cep/01001")
        self.assertEqual(resp.status_code, 400)
        data = json.loads(resp.get_data(as_text=True))
        self.assertFalse(data.get("success"))
        self.assertEqual(data.get("codigo"), "cep_invalido")
        print("[OK] CEP incompleto tratado com status 400.")

    def test_endpoint_cep_inexistente(self):
        """Testa CEP inexistente 99999-999"""
        resp = self.client.get("/api/cep/99999-999")
        self.assertEqual(resp.status_code, 404)
        data = json.loads(resp.get_data(as_text=True))
        self.assertFalse(data.get("success"))
        self.assertEqual(data.get("codigo"), "cep_nao_encontrado")
        print("[OK] CEP inexistente tratado com status 404.")

    def test_formulario_cadastro_membro_possui_viacep(self):
        """Verifica se a tela de cadastro de membro renderiza data-sigi-cep"""
        resp = self.client.get("/membros/cadastro")
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        self.assertIn("data-sigi-cep", html)
        self.assertIn("sigi-cep.js", html)
        print("[OK] /membros/cadastro contém data-sigi-cep e script global.")

    def test_formulario_editar_membro_possui_viacep(self):
        """Verifica se a tela de edição de membro renderiza data-sigi-cep"""
        resp = self.client.get(f"/membros/editar/{self.membro.id}")
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        self.assertIn("data-sigi-cep", html)
        print("[OK] /membros/editar/<id> contém data-sigi-cep.")

    def test_formulario_visitante_possui_viacep(self):
        """Verifica se a tela pública de visitante renderiza data-sigi-cep"""
        link = PublicLink.query.filter_by(tipo="visitante", ativo=True).first()
        if not link:
            novo_hash = PublicLink.gerar_hash()
            link = PublicLink(tipo="visitante", hash=novo_hash, ativo=True)
            db.session.add(link)
            db.session.commit()

        resp = self.client.get(f"/membros/cadastro-visitante/{link.hash}")
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        self.assertIn("data-sigi-cep", html)
        self.assertIn("sigi-cep.js", html)
        print("[OK] /membros/cadastro-visitante/<hash> contém data-sigi-cep e script.")

    def test_formulario_igreja_possui_viacep(self):
        """Verifica se a tela de edição da igreja renderiza data-sigi-cep"""
        resp = self.client.get("/configuracoes/igreja/editar")
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        self.assertIn("data-sigi-cep", html)
        print("[OK] /configuracoes/igreja/editar contém data-sigi-cep.")


if __name__ == "__main__":
    unittest.main()
