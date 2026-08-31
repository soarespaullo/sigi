import unittest
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import User

class TestWysiwygPatrimonioFinanceiro(unittest.TestCase):
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
                    email="admin_wysiwyg@sigi.local",
                    is_admin=True
                )
                user.set_password("admin123")
                db.session.add(user)
                db.session.commit()
            self.user_id = user.id

    def login(self):
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(self.user_id)
            sess['_fresh'] = True

    def test_patrimonio_novo_wysiwyg(self):
        """Verifica se /patrimonios/novo possui o editor WYSIWYG configurado"""
        with self.app.app_context():
            self.login()
            resp = self.client.get("/patrimonios/novo")
            self.assertEqual(resp.status_code, 200)
            html = resp.get_data(as_text=True)
            self.assertIn('sigi-editor-wrapper', html)
            self.assertIn('descricaoEditorContainer', html)
            self.assertIn('descricao_input', html)
            self.assertIn('initSigiEditor', html)
            print("[OK] /patrimonios/novo validado com editor WYSIWYG.")

    def test_financeiro_entradas_wysiwyg(self):
        """Verifica se /financeiro/entradas possui o editor WYSIWYG configurado"""
        with self.app.app_context():
            self.login()
            resp = self.client.get("/financeiro/entradas")
            self.assertEqual(resp.status_code, 200)
            html = resp.get_data(as_text=True)
            self.assertIn('sigi-editor-wrapper', html)
            self.assertIn('observacoesEditorContainer', html)
            self.assertIn('observacoes_input', html)
            self.assertIn('initSigiEditor', html)
            print("[OK] /financeiro/entradas validado com editor WYSIWYG.")

    def test_financeiro_saidas_wysiwyg(self):
        """Verifica se /financeiro/saidas possui o editor WYSIWYG configurado"""
        with self.app.app_context():
            self.login()
            resp = self.client.get("/financeiro/saidas")
            self.assertEqual(resp.status_code, 200)
            html = resp.get_data(as_text=True)
            self.assertIn('sigi-editor-wrapper', html)
            self.assertIn('observacoesEditorContainer', html)
            self.assertIn('observacoes_input', html)
            self.assertIn('initSigiEditor', html)
            print("[OK] /financeiro/saidas validado com editor WYSIWYG.")

if __name__ == "__main__":
    unittest.main()
