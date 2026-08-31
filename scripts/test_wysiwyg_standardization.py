#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
🧪 Suíte de Testes Automatizados — Padronização WYSIWYG & Sanitização XSS
Valida que todos os campos convertidos para WYSIWYG no SiGI salvam,
sanitizam HTML contra ataques XSS e persistem com fidelidade no banco de dados.
"""

import os
import sys
import unittest
from datetime import datetime, date, timedelta

# Garante que o diretório raiz do projeto esteja no sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app, db
from app.models import User, Member, Carta, Certificado, Ata, Evento
from app.models.ebd import EbdConfig, EbdPeriodo, EbdClasse, EbdAula
from utils.sanitizer import sanitizar_html


class TestWysiwygStandardization(unittest.TestCase):

    def setUp(self):
        self.app = create_app()
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.app.config['TESTING'] = True
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()

        # Cria ou obtém usuário administrador para autenticação
        self.admin = User.query.filter_by(email="admin_wysiwyg@teste.com").first()
        if not self.admin:
            self.admin = User(
                nome="Admin Teste",
                email="admin_wysiwyg@teste.com",
                is_admin=True,
                ativo=True
            )
            self.admin.set_password("Senha123!")
            db.session.add(self.admin)
            db.session.commit()

        # Cria ou obtém membro para vínculo
        self.membro = Member.query.filter_by(email="membro_wysiwyg@teste.com").first()
        if not self.membro:
            self.membro = Member(
                nome="Membro Teste WYSIWYG",
                cpf="111.222.333-44",
                email="membro_wysiwyg@teste.com",
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

    def test_sanitizer_xss_protection(self):
        """Testa o comportamento do sanitizer com tags válidas e ataques maliciosos."""
        # 1. Conteúdo com formatação rica válida
        conteudo_valido = "<p>Olá <strong>Mundo</strong>!</p><ul><li>Item 1</li><li>Item 2</li></ul>"
        self.assertEqual(sanitizar_html(conteudo_valido), conteudo_valido)

        # 2. Injeção com script malicioso
        conteudo_xss = "<p>Texto normal</p><script>alert('XSS')</script>"
        resultado = sanitizar_html(conteudo_xss)
        self.assertNotIn("<script>", resultado)
        self.assertNotIn("alert", resultado)
        self.assertIn("Texto normal", resultado)

        # 3. Injeção com handler inline de evento (onerror, onclick)
        conteudo_handler = '<p><img src="x" onerror="alert(1)">Texto seguro</p>'
        resultado_handler = sanitizar_html(conteudo_handler)
        self.assertNotIn("onerror", resultado_handler)
        self.assertIn("Texto seguro", resultado_handler)

        # 4. Links inseguros (javascript:)
        conteudo_link_js = '<a href="javascript:alert(1)">Clique aqui</a>'
        resultado_link = sanitizar_html(conteudo_link_js)
        self.assertNotIn("javascript:", resultado_link)

    def test_cartas_pastorais_wysiwyg(self):
        """Testa criação e edição de Carta Pastoral com HTML rico e sanitização."""
        corpo_rico = "<h2>Carta de Recomendação</h2><p>Recomendamos com júbilo o <strong>Irmão em Cristo</strong>.</p>"
        xss_corpo = corpo_rico + "<script>alert('hack')</script>"

        # Criação
        response = self.client.post("/documentos/cartas/nova", data={
            "titulo": "Recomendação Oficial WYSIWYG",
            "corpo": xss_corpo,
            "remetente": "Pastor Titular",
            "destinatario": "Igreja Co-irmã",
            "cidade": "São Paulo/SP",
            "situacao": "enviado",
            "membro_id": self.membro.id,
            "data_emissao": "2026-08-29"
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)

        carta = Carta.query.filter_by(titulo="Recomendação Oficial WYSIWYG").first()
        self.assertIsNotNone(carta)
        self.assertIn("<h2>Carta de Recomendação</h2>", carta.corpo)
        self.assertIn("<strong>Irmão em Cristo</strong>", carta.corpo)
        self.assertNotIn("<script>", carta.corpo)

        # Visualização de detalhes
        res_detalhe = self.client.get(f"/documentos/cartas/{carta.id}")
        self.assertEqual(res_detalhe.status_code, 200)
        self.assertIn(b"sigi-rich-content", res_detalhe.data)

    def test_certificados_wysiwyg(self):
        """Testa criação e edição de Certificado com HTML rico e sanitização."""
        corpo_certificado = "<p>Certificamos que <strong>Rafael Maciel</strong> concluiu o curso com nota <em>10</em>.</p>"

        response = self.client.post("/documentos/certificados/novo", data={
            "titulo": "Certificado Formação Ministerial WYSIWYG",
            "corpo": corpo_certificado,
            "criado_por": "Rafael Maciel",
            "evento": "Escola de Líderes 2026",
            "data_emissao": "2026-08-29",
            "situacao": "aprovado"
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)

        cert = Certificado.query.filter_by(titulo="Certificado Formação Ministerial WYSIWYG").first()
        self.assertIsNotNone(cert)
        self.assertIn("<strong>Rafael Maciel</strong>", cert.corpo)

        # Visualização de detalhes
        res_detalhe = self.client.get(f"/documentos/certificados/{cert.id}")
        self.assertEqual(res_detalhe.status_code, 200)
        self.assertIn(b"sigi-rich-content", res_detalhe.data)

    def test_livro_de_atas_wysiwyg(self):
        """Testa criação de Ata de Reunião com Pauta, Deliberações e Observações ricas."""
        pauta_html = "<ol><li>Abertura e Oração</li><li>Apresentação do Relatório Financeiro</li></ol>"
        delib_html = "<ul><li><strong>Aprovado</strong> relatório de contas do mês.</li></ul>"
        obs_html = "<blockquote>Reunião encerrada em paz e harmonia às 21h30.</blockquote>"

        response = self.client.post("/documentos/atas/nova", data={
            "titulo": "Assembleia Geral Extraordinária WYSIWYG",
            "data_reuniao": "2026-08-29",
            "tipo": "Reunião",
            "local": "Templo Sede",
            "situacao": "Aprovado",
            "presidente": "Pr. Presidente",
            "secretario": "Sec. Executivo",
            "participantes": "Membros presentes",
            "pauta": pauta_html,
            "deliberacoes": delib_html,
            "observacoes": obs_html
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)

        ata = Ata.query.filter_by(titulo="Assembleia Geral Extraordinária WYSIWYG").first()
        self.assertIsNotNone(ata)
        self.assertIn("<ol><li>Abertura e Oração</li>", ata.pauta)
        self.assertIn("<strong>Aprovado</strong>", ata.deliberacoes)
        self.assertIn("<blockquote>Reunião encerrada", ata.observacoes)

        # Visualização de detalhes
        res_detalhe = self.client.get(f"/documentos/atas/{ata.id}")
        self.assertEqual(res_detalhe.status_code, 200)
        self.assertIn(b"sigi-rich-content", res_detalhe.data)

    def test_eventos_wysiwyg(self):
        """Testa cadastro e edição de Eventos com descrição formatada."""
        descricao_evento = "<h3>Programação Oficial:</h3><ul><li>19h00: Louvor</li><li>19h45: Mensagem</li></ul>"

        response = self.client.post("/eventos/novo", data={
            "titulo": "Congresso de Avivamento 2026 WYSIWYG",
            "descricao": descricao_evento,
            "tipo": "conferencia",
            "data_inicio": "2026-09-10T19:00",
            "data_fim": "2026-09-10T22:00",
            "local": "Auditório Central",
            "organizador": "Ministério Pastoral",
            "status": "confirmado"
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)

        evento = Evento.query.filter_by(titulo="Congresso de Avivamento 2026 WYSIWYG").first()
        self.assertIsNotNone(evento)
        self.assertIn("<h3>Programação Oficial:</h3>", evento.descricao)

        # Página pública do evento
        res_publico = self.client.get(f"/eventos/publico/{evento.public_token}")
        self.assertEqual(res_publico.status_code, 200)
        self.assertIn(b"sigi-rich-content", res_publico.data)

    def test_ebd_wysiwyg(self):
        """Testa campos WYSIWYG nos módulos da Escola Dominical (EBD)."""
        # 1. Config EBD
        res_config = self.client.post("/ebd/config", data={
            "nome": "EBD Central",
            "descricao": "<p>Diretrizes institucionais com <strong>amor e ensino</strong>.</p>",
            "dia_semana": "Domingo",
            "horario_inicio": "09:00",
            "horario_termino": "10:30",
            "coordenador_id": "0",
            "ativo": "y"
        }, follow_redirects=True)
        self.assertEqual(res_config.status_code, 200)
        config = EbdConfig.query.first()
        self.assertIn("<strong>amor e ensino</strong>", config.descricao)

        # 2. Período Letivo
        res_periodo = self.client.post("/ebd/periodos/novo", data={
            "nome": "4º Trimestre 2026 WYSIWYG",
            "data_inicio": "2026-10-01",
            "data_fim": "2026-12-31",
            "status": "em_andamento",
            "observacoes": "<p>Revista: <em>As Grandes Doutrinas da Graça</em></p>"
        }, follow_redirects=True)
        self.assertEqual(res_periodo.status_code, 200)
        periodo = EbdPeriodo.query.filter_by(nome="4º Trimestre 2026 WYSIWYG").first()
        self.assertIsNotNone(periodo)
        self.assertIn("<em>As Grandes Doutrinas da Graça</em>", periodo.observacoes)

        # 3. Classe EBD
        res_classe = self.client.post("/ebd/classes/nova", data={
            "nome": "Classe Jovens e Adultos WYSIWYG",
            "periodo_id": periodo.id,
            "faixa_etaria": "A partir de 18 anos",
            "sala": "Sala Principal",
            "capacidade": 50,
            "status": "ativa",
            "descricao": "<h4>Objetivos do Trimestre</h4><p>Estudo sistemático da epístola aos Romanos.</p>"
        }, follow_redirects=True)
        self.assertEqual(res_classe.status_code, 200)
        classe = EbdClasse.query.filter_by(nome="Classe Jovens e Adultos WYSIWYG").first()
        self.assertIsNotNone(classe)
        self.assertIn("<h4>Objetivos do Trimestre</h4>", classe.descricao)

        # Detalhes da classe
        res_det_classe = self.client.get(f"/ebd/classes/{classe.id}")
        self.assertEqual(res_det_classe.status_code, 200)
        self.assertIn(b"sigi-rich-content", res_det_classe.data)

        # 4. Aula EBD
        res_aula = self.client.post("/ebd/aulas/nova", data={
            "classe_id": classe.id,
            "professor_id": "0",
            "data_aula": "2026-10-04",
            "numero_licao": "Lição 01",
            "tema": "A Justificação pela Fé WYSIWYG",
            "resumo_conteudo": "<p>Texto bíblico: <strong>Romanos 5:1-11</strong>.</p>",
            "status": "realizada",
            "observacoes": "<p>Trazer Bíblias de estudo na próxima semana.</p>"
        }, follow_redirects=True)
        self.assertEqual(res_aula.status_code, 200)
        aula = EbdAula.query.filter_by(tema="A Justificação pela Fé WYSIWYG").first()
        self.assertIsNotNone(aula)
        self.assertIn("<strong>Romanos 5:1-11</strong>", aula.resumo_conteudo)
        self.assertIn("Trazer Bíblias", aula.observacoes)

    def test_cadastro_visitante_wysiwyg(self):
        """Valida que a tela pública de cadastro de visitante contém o editor WYSIWYG e persiste mensagens ricas."""
        from app.models import PublicLink

        link = PublicLink.query.filter_by(tipo="visitante", ativo=True).first()
        if not link:
            novo_hash = PublicLink.gerar_hash()
            link = PublicLink(tipo="visitante", hash=novo_hash, ativo=True)
            db.session.add(link)
            db.session.commit()

        # 1. Testar GET na tela de visitante
        res_get = self.client.get(f"/membros/cadastro-visitante/{link.hash}")
        self.assertEqual(res_get.status_code, 200)
        html = res_get.get_data(as_text=True)
        self.assertIn("sigi-editor-wrapper", html)
        self.assertIn("observacoesEditorContainer", html)
        self.assertIn("observacoes_input", html)
        self.assertIn("initSigiEditor", html)

        # 2. Testar POST com mensagem rica formatada
        res_post = self.client.post(f"/membros/cadastro-visitante/{link.hash}", data={
            "nome": "Visitante Teste WYSIWYG",
            "telefone": "(11) 98888-7766",
            "email": "visitante_wysiwyg@teste.com",
            "data_nascimento": "1995-05-20",
            "sexo": "Masculino",
            "estado_civil": "Solteiro",
            "observacoes": "<p>Peço oração pela minha <strong>família</strong> e saúde.</p>"
        }, follow_redirects=True)
        self.assertEqual(res_post.status_code, 200)

        visitante = Member.query.filter_by(email="visitante_wysiwyg@teste.com").first()
        self.assertIsNotNone(visitante)
        self.assertIn("<strong>família</strong>", visitante.observacoes)


if __name__ == "__main__":
    unittest.main()
