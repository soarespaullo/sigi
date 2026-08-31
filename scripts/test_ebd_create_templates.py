import unittest
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import User

class TestEbdCreateTemplates(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()

        with self.app.app_context():
            user = User.query.filter_by(is_admin=True).first()
            if not user:
                user = User.query.first()
            self.user_id = user.id if user else 1

    def login(self):
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(self.user_id)
            sess['_fresh'] = True

    def test_templates_standardization(self):
        with self.app.app_context():
            self.login()
            urls = [
                "/ebd/classes/nova",
                "/ebd/aulas/nova",
                "/ebd/matriculas/nova",
                "/ebd/professores/novo",
                "/ebd/periodos/novo"
            ]

            for url in urls:
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200, f"Falha ao acessar {url}")
                html = response.get_data(as_text=True)

                # Verifica que a classe restritiva não existe mais no formulário
                self.assertNotIn("col-lg-8 col-xl-7", html, f"Classe restritiva ainda presente em {url}")
                # Verifica que a seção padronizada existe
                self.assertIn("sigi-form-section-title", html, f"Seção sigi-form-section-title ausente em {url}")
                # Verifica botão Salvar / Ação padronizado
                self.assertIn("bi-check2-circle", html, f"Ícone padronizado bi-check2-circle ausente em {url}")
                # Verifica container fluido com padding
                self.assertIn("container-fluid px-lg-5", html, f"Container fluido ausente em {url}")
                print(f"[OK] URL {url} validada com 100% de conformidade visual e estrutural.")

if __name__ == "__main__":
    unittest.main()
