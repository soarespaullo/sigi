#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
🏛️ SiGI — Script Geral de Povoamento de Dados (Seed Master)
Popula todo o sistema com dados demonstrativos completos e realistas:
1. Dados da Igreja Sede
2. Membros, Oficiais, Crianças, Jovens e Visitantes (Crescimento Natural da Igreja 2025-2026)
3. Escola Bíblica Dominical (EBD - Classes, Professores, Matrículas, Aulas, Frequências)
4. Gestão de Patrimônio e Bens
5. Calendário de Eventos, Atas de Assembleia, Cartas Pastorais e Certificados
6. Lançamentos Financeiros (Fluxo de Caixa 2025-2026)
"""

import os
import sys
import importlib.util
from pathlib import Path
from datetime import datetime, date, timedelta
import random

# Ajusta path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from app import create_app, db
from app.models import Igreja, Member, User, Evento, Ata, Carta, Certificado, Patrimonio
from app.models.ebd import EbdConfig, EbdPeriodo, EbdClasse, EbdProfessor, EbdMatricula, EbdAula, EbdFrequencia
from app.models.financeiro import Financeiro

app = create_app()

def seed_igreja():
    print("🏛️ [1/6] Configurando Dados da Igreja Sede...")
    igreja = Igreja.query.first()
    if not igreja:
        igreja = Igreja(
            nome="Igreja Evangélica Comunidade da Graça — Sede",
            cnpj="12.345.678/0001-90",
            endereco="Av. das Nações Unidas, 1500 - Centro, São Paulo/SP",
            telefone="(11) 98765-4321",
            email="contato@comunidadedagraca.org.br",
            site="https://comunidadedagraca.org.br",
            pastor_responsavel="Pr. Carlos Eduardo da Silva",
            ano_fundacao=1998,
            versiculo_tema="Porque dEle, por Ele e para Ele são todas as coisas. (Romanos 11:36)"
        )
        db.session.add(igreja)
    else:
        igreja.nome = "Igreja Evangélica Comunidade da Graça — Sede"
        igreja.pastor_responsavel = "Pr. Carlos Eduardo da Silva"
        igreja.versiculo_tema = "Porque dEle, por Ele e para Ele são todas as coisas. (Romanos 11:36)"
    db.session.commit()
    print("  ✅ Dados da Igreja configurados com sucesso.")

def seed_membros():
    print("👥 [2/6] Cadastrando Membros, Oficiais, Crianças, Jovens e Visitantes...")
    
    # Limpa membros para garantir histórico consistente de crescimento
    Member.query.delete()
    db.session.commit()

    membros_completos = [
        # Liderança Pastoral e Diaconal
        {"nome": "Pr. Carlos Eduardo da Silva", "sexo": "Masculino", "estado_civil": "Casado", "conjuge": "Pra. Helena Silva", "telefone": "(11) 98111-1001", "email": "pastorcarlos@sigi.local", "funcao": "Pastor Titular", "dizimista": True, "batizado": True, "nasc": date(1975, 4, 12), "batismo": date(1992, 10, 15), "cad": date(2025, 1, 5), "saida": None, "status": "Ativo", "vis": False, "cpf": "111.222.333-44", "rg": "22.333.444-5", "endereco": "Av. Paulista, 1000", "bairro": "Bela Vista", "cep": "01310-100", "obs": "<p>Pastor Titular presidente do ministério.</p>"},
        {"nome": "Pra. Helena Beatriz Silva", "sexo": "Feminino", "estado_civil": "Casada", "conjuge": "Pr. Carlos Eduardo da Silva", "telefone": "(11) 98111-1002", "email": "pastorahelena@sigi.local", "funcao": "Pastora Auxiliar", "dizimista": True, "batizado": True, "nasc": date(1978, 8, 24), "batismo": date(1995, 6, 20), "cad": date(2025, 1, 5), "saida": None, "status": "Ativo", "vis": False, "cpf": "222.333.444-55", "rg": "33.444.555-6", "endereco": "Av. Paulista, 1000", "bairro": "Bela Vista", "cep": "01310-100", "obs": "<p>Líder do Ministério de Famílias e Ação Social.</p>"},
        {"nome": "Presb. Marcos Roberto Santos", "sexo": "Masculino", "estado_civil": "Casado", "conjuge": "Débora Santos", "telefone": "(11) 98222-2001", "email": "marcos.santos@gmail.com", "funcao": "Presbítero", "dizimista": True, "batizado": True, "nasc": date(1980, 2, 10), "batismo": date(2000, 3, 12), "cad": date(2025, 1, 10), "saida": None, "status": "Ativo", "vis": False, "cpf": "333.444.555-66", "rg": "44.555.666-7", "endereco": "Rua Augusta, 450", "bairro": "Consolação", "cep": "01304-000", "obs": "<p>Superintendente da Escola Bíblica Dominical.</p>"},
        {"nome": "Diác. André Luiz Ferreira", "sexo": "Masculino", "estado_civil": "Casado", "conjuge": "Mariana Ferreira", "telefone": "(11) 98333-3001", "email": "andre.ferreira@hotmail.com", "funcao": "Diácono", "dizimista": True, "batizado": True, "nasc": date(1985, 11, 5), "batismo": date(2005, 11, 20), "cad": date(2025, 1, 15), "saida": None, "status": "Ativo", "vis": False, "cpf": "444.555.666-77", "rg": "55.666.777-8", "endereco": "Rua Domingos de Morais, 1200", "bairro": "Vila Mariana", "cep": "04010-100", "obs": "<p>Líder da equipe de Diaconia e Recepção.</p>"},
        {"nome": "Diác. Juliana Souza Mendes", "sexo": "Feminino", "estado_civil": "Solteira", "conjuge": "", "telefone": "(11) 98333-3002", "email": "juliana.mendes@gmail.com", "funcao": "Diaconisa", "dizimista": True, "batizado": True, "nasc": date(1990, 7, 18), "batismo": date(2010, 4, 15), "cad": date(2025, 1, 20), "saida": None, "status": "Ativo", "vis": False, "cpf": "555.666.777-88", "rg": "66.777.888-9", "endereco": "Rua Vergueiro, 800", "bairro": "Paraíso", "cep": "01504-001", "obs": "<p>Coordenação do Ministério de Oração e Intercessão.</p>"},

        # Professores e Líderes
        {"nome": "Prof. Roberto Albuquerque", "sexo": "Masculino", "estado_civil": "Casado", "conjuge": "Renata Albuquerque", "telefone": "(11) 98444-4001", "email": "roberto.ebd@sigi.local", "funcao": "Professor EBD", "dizimista": True, "batizado": True, "nasc": date(1982, 9, 14), "batismo": date(1998, 8, 10), "cad": date(2025, 2, 8), "saida": None, "status": "Ativo", "vis": False, "cpf": "666.777.888-99", "rg": "77.888.999-0", "endereco": "Rua Pamplona, 320", "bairro": "Jardim Paulista", "cep": "01405-000", "obs": "<p>Professor da Classe de Adultos da EBD.</p>"},
        {"nome": "Profa. Amanda Lima Rocha", "sexo": "Feminino", "estado_civil": "Casada", "conjuge": "Lucas Rocha", "telefone": "(11) 98444-4002", "email": "amanda.rocha@yahoo.com", "funcao": "Professora Infantil", "dizimista": True, "batizado": True, "nasc": date(1992, 3, 29), "batismo": date(2012, 12, 16), "cad": date(2025, 2, 15), "saida": None, "status": "Ativo", "vis": False, "cpf": "777.888.999-00", "rg": "88.999.000-1", "endereco": "Rua Oscar Freire, 950", "bairro": "Cerqueira César", "cep": "01426-001", "obs": "<p>Professora do Departamento Infantil.</p>"},
        {"nome": "Gabriel Tavares Castro", "sexo": "Masculino", "estado_civil": "Solteiro", "conjuge": "", "telefone": "(11) 98555-5001", "email": "gabriel.jovens@gmail.com", "funcao": "Líder de Jovens", "dizimista": True, "batizado": True, "nasc": date(2001, 5, 20), "batismo": date(2018, 10, 28), "cad": date(2025, 2, 22), "saida": None, "status": "Ativo", "vis": False, "cpf": "888.999.000-11", "rg": "99.000.111-2", "endereco": "Rua Haddock Lobo, 600", "bairro": "Cerqueira César", "cep": "01414-001", "obs": "<p>Líder do Ministério de Jovens Conectados.</p>"},
        {"nome": "Beatriz Martins Oliveira", "sexo": "Feminino", "estado_civil": "Solteira", "conjuge": "", "telefone": "(11) 98555-5002", "email": "bia.louvor@gmail.com", "funcao": "Líder de Louvor", "dizimista": True, "batizado": True, "nasc": date(1999, 12, 3), "batismo": date(2016, 7, 24), "cad": date(2025, 3, 5), "saida": None, "status": "Ativo", "vis": False, "cpf": "999.000.111-22", "rg": "10.111.222-3", "endereco": "Rua da Consolação, 2100", "bairro": "Consolação", "cep": "01301-100", "obs": "<p>Ministra de Louvor e Regente do Coral.</p>"},

        # Adultos e Famílias
        {"nome": "Antônio Carlos de Almeida", "sexo": "Masculino", "estado_civil": "Casado", "conjuge": "Maria Aparecida Almeida", "telefone": "(11) 98666-6001", "email": "antonio.almeida@uol.com.br", "funcao": "Membro", "dizimista": True, "batizado": True, "nasc": date(1968, 6, 15), "batismo": date(1989, 5, 14), "cad": date(2025, 3, 18), "saida": None, "status": "Ativo", "vis": False, "cpf": "123.456.789-01", "rg": "11.222.333-4", "endereco": "Rua Frei Caneca, 700", "bairro": "Consolação", "cep": "01307-001", "obs": ""},
        {"nome": "Maria Aparecida Almeida", "sexo": "Feminino", "estado_civil": "Casada", "conjuge": "Antônio Carlos de Almeida", "telefone": "(11) 98666-6002", "email": "maria.aparecida@uol.com.br", "funcao": "Membro", "dizimista": True, "batizado": True, "nasc": date(1971, 10, 8), "batismo": date(1990, 4, 22), "cad": date(2025, 3, 18), "saida": None, "status": "Ativo", "vis": False, "cpf": "234.567.890-12", "rg": "22.333.444-5", "endereco": "Rua Frei Caneca, 700", "bairro": "Consolação", "cep": "01307-001", "obs": ""},
        {"nome": "Lucas Barbosa Ramos", "sexo": "Masculino", "estado_civil": "Solteiro", "conjuge": "", "telefone": "(11) 98777-7001", "email": "lucas.ramos98@gmail.com", "funcao": "Membro", "dizimista": True, "batizado": True, "nasc": date(1998, 1, 25), "batismo": date(2017, 9, 10), "cad": date(2025, 4, 12), "saida": None, "status": "Ativo", "vis": False, "cpf": "345.678.901-23", "rg": "33.444.555-6", "endereco": "Rua Bela Cintra, 1400", "bairro": "Consolação", "cep": "01415-000", "obs": ""},
        {"nome": "Fernanda Ribeiro Costa", "sexo": "Feminino", "estado_civil": "Casada", "conjuge": "Thiago Costa", "telefone": "(11) 98777-7002", "email": "fernanda.costa@hotmail.com", "funcao": "Membro", "dizimista": True, "batizado": True, "nasc": date(1988, 11, 30), "batismo": date(2008, 11, 23), "cad": date(2025, 4, 25), "saida": None, "status": "Ativo", "vis": False, "cpf": "456.789.012-34", "rg": "44.555.666-7", "endereco": "Alameda Santos, 1800", "bairro": "Cerqueira César", "cep": "01418-200", "obs": ""},
        {"nome": "Thiago Monteiro Costa", "sexo": "Masculino", "estado_civil": "Casado", "conjuge": "Fernanda Ribeiro Costa", "telefone": "(11) 98777-7003", "email": "thiago.monteiro@hotmail.com", "funcao": "Membro", "dizimista": True, "batizado": True, "nasc": date(1986, 4, 17), "batismo": date(2006, 8, 13), "cad": date(2025, 4, 25), "saida": None, "status": "Ativo", "vis": False, "cpf": "567.890.123-45", "rg": "55.666.777-8", "endereco": "Alameda Santos, 1800", "bairro": "Cerqueira César", "cep": "01418-200", "obs": ""},
        {"nome": "Larissa Gomes Peixoto", "sexo": "Feminino", "estado_civil": "Solteira", "conjuge": "", "telefone": "(11) 98888-8001", "email": "larissa.peixoto@gmail.com", "funcao": "Membro", "dizimista": True, "batizado": True, "nasc": date(2003, 7, 12), "batismo": date(2021, 6, 27), "cad": date(2025, 5, 14), "saida": None, "status": "Ativo", "vis": False, "cpf": "678.901.234-56", "rg": "66.777.888-9", "endereco": "Rua Treze de Maio, 500", "bairro": "Bixiga", "cep": "01327-000", "obs": ""},
        {"nome": "Matheus Henrique Dias", "sexo": "Masculino", "estado_civil": "Solteiro", "conjuge": "", "telefone": "(11) 98888-8002", "email": "matheus.dias@gmail.com", "funcao": "Membro", "dizimista": False, "batizado": True, "nasc": date(2005, 3, 19), "batismo": date(2023, 12, 10), "cad": date(2025, 5, 29), "saida": None, "status": "Ativo", "vis": False, "cpf": "789.012.345-67", "rg": "77.888.999-0", "endereco": "Rua Maria Antônia, 250", "bairro": "Higienópolis", "cep": "01222-010", "obs": ""},
        {"nome": "Paulo Sérgio Guimarães", "sexo": "Masculino", "estado_civil": "Casado", "conjuge": "Sônia Guimarães", "telefone": "(11) 98999-1001", "email": "paulo.guimaraes@gmail.com", "funcao": "Membro", "dizimista": True, "batizado": True, "nasc": date(1964, 8, 19), "batismo": date(1985, 3, 10), "cad": date(2025, 6, 10), "saida": None, "status": "Ativo", "vis": False, "cpf": "890.123.456-78", "rg": "88.999.000-1", "endereco": "Av. Brigadeiro Luís Antônio, 2200", "bairro": "Jardim Paulista", "cep": "01402-002", "obs": ""},
        {"nome": "Sônia Regina Guimarães", "sexo": "Feminino", "estado_civil": "Casada", "conjuge": "Paulo Sérgio Guimarães", "telefone": "(11) 98999-1002", "email": "sonia.guimaraes@gmail.com", "funcao": "Membro", "dizimista": True, "batizado": True, "nasc": date(1967, 1, 30), "batismo": date(1987, 7, 15), "cad": date(2025, 6, 10), "saida": None, "status": "Ativo", "vis": False, "cpf": "901.234.567-89", "rg": "99.000.111-2", "endereco": "Av. Brigadeiro Luís Antônio, 2200", "bairro": "Jardim Paulista", "cep": "01402-002", "obs": ""},
        {"nome": "Eduardo Cavalcanti", "sexo": "Masculino", "estado_civil": "Solteiro", "conjuge": "", "telefone": "(11) 98999-2001", "email": "edu.cavalcanti@terra.com.br", "funcao": "Membro", "dizimista": True, "batizado": True, "nasc": date(1993, 10, 5), "batismo": date(2014, 5, 18), "cad": date(2025, 7, 15), "saida": None, "status": "Ativo", "vis": False, "cpf": "012.345.678-90", "rg": "10.111.222-3", "endereco": "Rua Cincinato Braga, 340", "bairro": "Bela Vista", "cep": "01333-010", "obs": ""},
        {"nome": "Priscila Nogueira", "sexo": "Feminino", "estado_civil": "Solteira", "conjuge": "", "telefone": "(11) 98999-2002", "email": "pri.nogueira@gmail.com", "funcao": "Membro", "dizimista": True, "batizado": True, "nasc": date(1995, 6, 12), "batismo": date(2015, 9, 20), "cad": date(2025, 8, 20), "saida": None, "status": "Ativo", "vis": False, "cpf": "123.456.789-02", "rg": "21.322.433-5", "endereco": "Alameda Jaú, 1100", "bairro": "Jardim Paulista", "cep": "01420-001", "obs": ""},
        {"nome": "Rodrigo Valente", "sexo": "Masculino", "estado_civil": "Casado", "conjuge": "Flávia Valente", "telefone": "(11) 98999-3001", "email": "rodrigo.valente@uol.com.br", "funcao": "Membro", "dizimista": True, "batizado": True, "nasc": date(1981, 12, 1), "batismo": date(2002, 4, 14), "cad": date(2025, 9, 12), "saida": None, "status": "Ativo", "vis": False, "cpf": "234.567.890-13", "rg": "32.433.544-6", "endereco": "Rua Cubatão, 580", "bairro": "Vila Mariana", "cep": "04013-002", "obs": ""},
        {"nome": "Flávia Valente", "sexo": "Feminino", "estado_civil": "Casada", "conjuge": "Rodrigo Valente", "telefone": "(11) 98999-3002", "email": "flavia.valente@uol.com.br", "funcao": "Membro", "dizimista": True, "batizado": True, "nasc": date(1983, 5, 18), "batismo": date(2004, 10, 22), "cad": date(2025, 9, 12), "saida": None, "status": "Ativo", "vis": False, "cpf": "345.678.901-24", "rg": "43.544.655-7", "endereco": "Rua Cubatão, 580", "bairro": "Vila Mariana", "cep": "04013-002", "obs": ""},
        {"nome": "Vitor Hugo Silveira", "sexo": "Masculino", "estado_civil": "Solteiro", "conjuge": "", "telefone": "(11) 98999-4001", "email": "vitor.silveira@gmail.com", "funcao": "Membro", "dizimista": True, "batizado": True, "nasc": date(2000, 2, 14), "batismo": date(2019, 11, 17), "cad": date(2025, 10, 8), "saida": None, "status": "Ativo", "vis": False, "cpf": "456.789.012-35", "rg": "54.655.766-8", "endereco": "Rua Peixoto Gomide, 900", "bairro": "Jardim Paulista", "cep": "01409-001", "obs": ""},
        {"nome": "Cláudia Meireles", "sexo": "Feminino", "estado_civil": "Divorciada", "conjuge": "", "telefone": "(11) 98999-5001", "email": "claudia.meireles@gmail.com", "funcao": "Membro", "dizimista": True, "batizado": True, "nasc": date(1974, 9, 27), "batismo": date(1996, 8, 11), "cad": date(2025, 11, 18), "saida": None, "status": "Ativo", "vis": False, "cpf": "567.890.123-46", "rg": "65.766.877-9", "endereco": "Rua Itapeva, 400", "bairro": "Bela Vista", "cep": "01332-000", "obs": ""},
        {"nome": "Leandro Barreto", "sexo": "Masculino", "estado_civil": "Solteiro", "conjuge": "", "telefone": "(11) 98999-6001", "email": "leandro.barreto@gmail.com", "funcao": "Membro", "dizimista": True, "batizado": True, "nasc": date(1996, 4, 3), "batismo": date(2016, 12, 18), "cad": date(2025, 12, 10), "saida": None, "status": "Ativo", "vis": False, "cpf": "678.901.234-57", "rg": "76.877.988-0", "endereco": "Rua Pamplona, 1100", "bairro": "Jardim Paulista", "cep": "01405-001", "obs": ""},

        # Entradas em 2026
        {"nome": "Guilherme Siqueira", "sexo": "Masculino", "estado_civil": "Casado", "conjuge": "Tatiane Siqueira", "telefone": "(11) 97111-1001", "email": "gui.siqueira@gmail.com", "funcao": "Membro", "dizimista": True, "batizado": True, "nasc": date(1989, 7, 21), "batismo": date(2010, 6, 13), "cad": date(2026, 1, 14), "saida": None, "status": "Ativo", "vis": False, "cpf": "789.012.345-68", "rg": "87.988.099-1", "endereco": "Alameda Lorena, 1500", "bairro": "Jardim Paulista", "cep": "01424-001", "obs": ""},
        {"nome": "Tatiane Siqueira", "sexo": "Feminino", "estado_civil": "Casada", "conjuge": "Guilherme Siqueira", "telefone": "(11) 97111-1002", "email": "tati.siqueira@gmail.com", "funcao": "Membro", "dizimista": True, "batizado": True, "nasc": date(1991, 11, 15), "batismo": date(2011, 8, 21), "cad": date(2026, 1, 14), "saida": None, "status": "Ativo", "vis": False, "cpf": "890.123.456-79", "rg": "98.099.100-2", "endereco": "Alameda Lorena, 1500", "bairro": "Jardim Paulista", "cep": "01424-001", "obs": ""},
        {"nome": "Felipe Augusto Fonseca", "sexo": "Masculino", "estado_civil": "Solteiro", "conjuge": "", "telefone": "(11) 97222-2001", "email": "felipe.fonseca@gmail.com", "funcao": "Membro", "dizimista": True, "batizado": True, "nasc": date(2002, 8, 9), "batismo": date(2022, 10, 16), "cad": date(2026, 2, 18), "saida": None, "status": "Ativo", "vis": False, "cpf": "901.234.567-80", "rg": "09.100.211-3", "endereco": "Rua Tutóia, 650", "bairro": "Vila Mariana", "cep": "04007-003", "obs": ""},
        {"nome": "Renata Antunes", "sexo": "Feminino", "estado_civil": "Solteira", "conjuge": "", "telefone": "(11) 97333-3001", "email": "renata.antunes@gmail.com", "funcao": "Membro", "dizimista": True, "batizado": True, "nasc": date(1994, 3, 17), "batismo": date(2015, 4, 12), "cad": date(2026, 3, 22), "saida": None, "status": "Ativo", "vis": False, "cpf": "012.345.678-91", "rg": "10.211.322-4", "endereco": "Rua Abílio Soares, 800", "bairro": "Paraíso", "cep": "04005-003", "obs": ""},
        {"nome": "Alexandre Pires Moraes", "sexo": "Masculino", "estado_civil": "Casado", "conjuge": "Bárbara Moraes", "telefone": "(11) 97444-4001", "email": "alex.moraes@gmail.com", "funcao": "Membro", "dizimista": True, "batizado": True, "nasc": date(1987, 12, 28), "batismo": date(2007, 7, 8), "cad": date(2026, 4, 19), "saida": None, "status": "Ativo", "vis": False, "cpf": "123.456.789-03", "rg": "21.322.433-6", "endereco": "Rua Maestro Cardim, 900", "bairro": "Bela Vista", "cep": "01323-001", "obs": ""},
        {"nome": "Bárbara Moraes", "sexo": "Feminino", "estado_civil": "Casada", "conjuge": "Alexandre Pires Moraes", "telefone": "(11) 97444-4002", "email": "barbara.moraes@gmail.com", "funcao": "Membro", "dizimista": True, "batizado": True, "nasc": date(1989, 9, 4), "batismo": date(2009, 10, 18), "cad": date(2026, 4, 19), "saida": None, "status": "Ativo", "vis": False, "cpf": "234.567.890-14", "rg": "32.433.544-7", "endereco": "Rua Maestro Cardim, 900", "bairro": "Bela Vista", "cep": "01323-001", "obs": ""},
        {"nome": "Danilo Fagundes", "sexo": "Masculino", "estado_civil": "Solteiro", "conjuge": "", "telefone": "(11) 97555-5001", "email": "danilo.fagundes@gmail.com", "funcao": "Membro", "dizimista": True, "batizado": True, "nasc": date(2004, 1, 11), "batismo": date(2024, 6, 23), "cad": date(2026, 5, 25), "saida": None, "status": "Ativo", "vis": False, "cpf": "345.678.901-25", "rg": "43.544.655-8", "endereco": "Rua São Carlos do Pinhal, 300", "bairro": "Bela Vista", "cep": "01333-000", "obs": ""},
        {"nome": "Letícia Camargo", "sexo": "Feminino", "estado_civil": "Solteira", "conjuge": "", "telefone": "(11) 97666-6001", "email": "leticia.camargo@gmail.com", "funcao": "Membro", "dizimista": True, "batizado": True, "nasc": date(1997, 8, 30), "batismo": date(2018, 5, 20), "cad": date(2026, 6, 16), "saida": None, "status": "Ativo", "vis": False, "cpf": "456.789.012-36", "rg": "54.655.766-9", "endereco": "Alameda Campinas, 750", "bairro": "Jardim Paulista", "cep": "01404-000", "obs": ""},
        {"nome": "Gustavo Peçanha", "sexo": "Masculino", "estado_civil": "Solteiro", "conjuge": "", "telefone": "(11) 97777-7001", "email": "gustavo.pecanha@gmail.com", "funcao": "Membro", "dizimista": True, "batizado": True, "nasc": date(2001, 10, 14), "batismo": date(2020, 11, 15), "cad": date(2026, 7, 20), "saida": None, "status": "Ativo", "vis": False, "cpf": "567.890.123-47", "rg": "65.766.877-0", "endereco": "Alameda Ministro Rocha Azevedo, 450", "bairro": "Cerqueira César", "cep": "01410-001", "obs": ""},
        {"nome": "Aline Medeiros", "sexo": "Feminino", "estado_civil": "Solteira", "conjuge": "", "telefone": "(11) 97888-8001", "email": "aline.medeiros@gmail.com", "funcao": "Membro", "dizimista": True, "batizado": True, "nasc": date(1998, 4, 26), "batismo": date(2017, 8, 13), "cad": date(2026, 8, 12), "saida": None, "status": "Ativo", "vis": False, "cpf": "678.901.234-58", "rg": "76.877.988-1", "endereco": "Rua Bela Cintra, 800", "bairro": "Consolação", "cep": "01415-000", "obs": ""},

        # Crianças (Maternal / Primários - EBD)
        {"nome": "Davi Silva Santos", "sexo": "Masculino", "estado_civil": "Solteiro", "conjuge": "", "telefone": "(11) 98222-2001", "email": "", "funcao": "Criança / EBD", "dizimista": False, "batizado": False, "nasc": date(2021, 9, 8), "batismo": None, "cad": date(2025, 2, 10), "saida": None, "status": "Ativo", "vis": False, "cpf": "", "rg": "", "endereco": "Rua Augusta, 450", "bairro": "Consolação", "cep": "01304-000", "obs": "<p>Apresentado no templo em 15/10/2021.</p>"},
        {"nome": "Sarah Albuquerque", "sexo": "Feminino", "estado_civil": "Solteira", "conjuge": "", "telefone": "(11) 98444-4001", "email": "", "funcao": "Criança / EBD", "dizimista": False, "batizado": False, "nasc": date(2022, 4, 15), "batismo": None, "cad": date(2025, 3, 10), "saida": None, "status": "Ativo", "vis": False, "cpf": "", "rg": "", "endereco": "Rua Pamplona, 320", "bairro": "Jardim Paulista", "cep": "01405-000", "obs": "<p>Apresentada no templo em 20/06/2022.</p>"},
        {"nome": "Enzo Gabriel Rocha", "sexo": "Masculino", "estado_civil": "Solteiro", "conjuge": "", "telefone": "(11) 98444-4002", "email": "", "funcao": "Criança / EBD", "dizimista": False, "batizado": False, "nasc": date(2020, 11, 20), "batismo": None, "cad": date(2025, 3, 15), "saida": None, "status": "Ativo", "vis": False, "cpf": "", "rg": "", "endereco": "Rua Oscar Freire, 950", "bairro": "Cerqueira César", "cep": "01426-001", "obs": ""},
        {"nome": "Manuela Costa", "sexo": "Feminino", "estado_civil": "Solteira", "conjuge": "", "telefone": "(11) 98777-7002", "email": "", "funcao": "Primários / EBD", "dizimista": False, "batizado": False, "nasc": date(2017, 6, 14), "batismo": None, "cad": date(2025, 4, 25), "saida": None, "status": "Ativo", "vis": False, "cpf": "", "rg": "", "endereco": "Alameda Santos, 1800", "bairro": "Cerqueira César", "cep": "01418-200", "obs": ""},
        {"nome": "Pedro Henrique Valente", "sexo": "Masculino", "estado_civil": "Solteiro", "conjuge": "", "telefone": "(11) 98999-3001", "email": "", "funcao": "Primários / EBD", "dizimista": False, "batizado": False, "nasc": date(2016, 2, 28), "batismo": None, "cad": date(2025, 9, 12), "saida": None, "status": "Ativo", "vis": False, "cpf": "", "rg": "", "endereco": "Rua Cubatão, 580", "bairro": "Vila Mariana", "cep": "04013-002", "obs": ""},
        {"nome": "Heloísa Siqueira", "sexo": "Feminino", "estado_civil": "Solteira", "conjuge": "", "telefone": "(11) 97111-1001", "email": "", "funcao": "Primários / EBD", "dizimista": False, "batizado": False, "nasc": date(2018, 10, 5), "batismo": None, "cad": date(2026, 1, 14), "saida": None, "status": "Ativo", "vis": False, "cpf": "", "rg": "", "endereco": "Alameda Lorena, 1500", "bairro": "Jardim Paulista", "cep": "01424-001", "obs": ""},

        # Adolescentes (EBD)
        {"nome": "Samuel Costa Ramos", "sexo": "Masculino", "estado_civil": "Solteiro", "conjuge": "", "telefone": "(11) 98777-7002", "email": "samuel.costa@gmail.com", "funcao": "Adolescente", "dizimista": False, "batizado": False, "nasc": date(2012, 11, 2), "batismo": None, "cad": date(2025, 4, 25), "saida": None, "status": "Ativo", "vis": False, "cpf": "", "rg": "", "endereco": "Alameda Santos, 1800", "bairro": "Cerqueira César", "cep": "01418-200", "obs": ""},
        {"nome": "Isabela Guimarães", "sexo": "Feminino", "estado_civil": "Solteira", "conjuge": "", "telefone": "(11) 98999-1001", "email": "isabela.guimaraes@gmail.com", "funcao": "Adolescente", "dizimista": False, "batizado": False, "nasc": date(2010, 8, 17), "batismo": None, "cad": date(2025, 6, 10), "saida": None, "status": "Ativo", "vis": False, "cpf": "", "rg": "", "endereco": "Av. Brigadeiro Luís Antônio, 2200", "bairro": "Jardim Paulista", "cep": "01402-002", "obs": ""},
        {"nome": "Lucas Gabriel Meireles", "sexo": "Masculino", "estado_civil": "Solteiro", "conjuge": "", "telefone": "(11) 98999-5001", "email": "lucas.meireles@gmail.com", "funcao": "Adolescente", "dizimista": False, "batizado": False, "nasc": date(2011, 5, 23), "batismo": None, "cad": date(2025, 11, 18), "saida": None, "status": "Ativo", "vis": False, "cpf": "", "rg": "", "endereco": "Rua Itapeva, 400", "bairro": "Bela Vista", "cep": "01332-000", "obs": ""},
        {"nome": "Rebeca Moraes", "sexo": "Feminino", "estado_civil": "Solteira", "conjuge": "", "telefone": "(11) 97444-4001", "email": "rebeca.moraes@gmail.com", "funcao": "Adolescente", "dizimista": False, "batizado": False, "nasc": date(2013, 1, 30), "batismo": None, "cad": date(2026, 4, 19), "saida": None, "status": "Ativo", "vis": False, "cpf": "", "rg": "", "endereco": "Rua Maestro Cardim, 900", "bairro": "Bela Vista", "cep": "01323-001", "obs": ""},

        # Membros Transferidos (Saída formal por carta de transferência para outra igreja)
        {"nome": "Marcelo Dantas", "sexo": "Masculino", "estado_civil": "Casado", "conjuge": "Márcia Dantas", "telefone": "(11) 96111-1001", "email": "marcelo.dantas@uol.com.br", "funcao": "Membro", "dizimista": True, "batizado": True, "nasc": date(1979, 3, 14), "batismo": date(1999, 5, 10), "cad": date(2025, 1, 10), "saida": date(2025, 6, 30), "status": "Transferido", "vis": False, "cpf": "789.012.345-69", "rg": "89.011.122-3", "endereco": "Rua Vergueiro, 1500", "bairro": "Vila Mariana", "cep": "04101-000", "obs": "<p>Transferido por solicitação pastoral para a Igreja Batista Central em Curitiba/PR. Carta emitida em 30/06/2025.</p>"},
        {"nome": "Márcia Dantas", "sexo": "Feminino", "estado_civil": "Casada", "conjuge": "Marcelo Dantas", "telefone": "(11) 96111-1002", "email": "marcia.dantas@uol.com.br", "funcao": "Membro", "dizimista": True, "batizado": True, "nasc": date(1982, 7, 20), "batismo": date(2001, 8, 15), "cad": date(2025, 1, 10), "saida": date(2025, 6, 30), "status": "Transferido", "vis": False, "cpf": "890.123.456-80", "rg": "90.122.233-4", "endereco": "Rua Vergueiro, 1500", "bairro": "Vila Mariana", "cep": "04101-000", "obs": "<p>Transferida junto ao esposo Marcelo Dantas para Curitiba/PR.</p>"},
        {"nome": "Jorge Bastos", "sexo": "Masculino", "estado_civil": "Solteiro", "conjuge": "", "telefone": "(11) 96222-2001", "email": "jorge.bastos@gmail.com", "funcao": "Membro", "dizimista": True, "batizado": True, "nasc": date(1992, 11, 4), "batismo": date(2013, 9, 22), "cad": date(2025, 3, 15), "saida": date(2026, 4, 15), "status": "Transferido", "vis": False, "cpf": "901.234.567-81", "rg": "01.233.344-5", "endereco": "Rua Cardeal Arcoverde, 1200", "bairro": "Pinheiros", "cep": "05408-001", "obs": "<p>Transferido para a Igreja Presbiteriana de Campinas/SP por motivo de estudos/trabalho.</p>"},

        # Membros Inativos / Desligados
        {"nome": "Renata Vilela", "sexo": "Feminino", "estado_civil": "Solteira", "conjuge": "", "telefone": "(11) 96333-3001", "email": "renata.vilela@gmail.com", "funcao": "Membro", "dizimista": True, "batizado": True, "nasc": date(1996, 6, 19), "batismo": date(2017, 10, 15), "cad": date(2025, 5, 10), "saida": date(2026, 3, 31), "status": "Inativo", "vis": False, "cpf": "012.345.678-92", "rg": "12.344.455-6", "endereco": "Rua Teodoro Sampaio, 850", "bairro": "Pinheiros", "cep": "05406-000", "obs": "<p>Mudou-se para o exterior (Canadá). Cadastro inativado a pedido.</p>"},
        {"nome": "Cláudio Mendonça", "sexo": "Masculino", "estado_civil": "Casado", "conjuge": "Denise Mendonça", "telefone": "(11) 96444-4001", "email": "claudio.mendonca@gmail.com", "funcao": "Membro", "dizimista": True, "batizado": True, "nasc": date(1973, 10, 12), "batismo": date(1994, 4, 18), "cad": date(2025, 2, 20), "saida": date(2026, 7, 15), "status": "Inativo", "vis": False, "cpf": "123.456.789-04", "rg": "23.455.566-7", "endereco": "Rua Fradique Coutinho, 500", "bairro": "Pinheiros", "cep": "05416-000", "obs": "<p>Desligamento a pedido por mudança de domicílio.</p>"},

        # Visitantes
        {"nome": "Julio Cesar Brandão", "sexo": "Masculino", "estado_civil": "Casado", "conjuge": "Renata Brandão", "telefone": "(11) 99123-4567", "email": "julio.brandao@outlook.com", "funcao": "Visitante", "dizimista": False, "batizado": False, "nasc": date(1984, 8, 22), "batismo": None, "cad": date(2026, 8, 10), "saida": None, "status": "Ativo", "vis": True, "cpf": "", "rg": "", "endereco": "Rua Henrique Schaumann, 400", "bairro": "Pinheiros", "cep": "05413-010", "obs": "<p>Visitante do culto de domingo. Convidado pelo Diác. André.</p>"},
        {"nome": "Camila Vasconcelos", "sexo": "Feminino", "estado_civil": "Solteira", "conjuge": "", "telefone": "(11) 99876-5432", "email": "camila.vasconcelos@gmail.com", "funcao": "Visitante", "dizimista": False, "batizado": False, "nasc": date(1997, 5, 14), "batismo": None, "cad": date(2026, 8, 17), "saida": None, "status": "Ativo", "vis": True, "cpf": "", "rg": "", "endereco": "Rua Mourato Coelho, 600", "bairro": "Pinheiros", "cep": "05417-001", "obs": "<p>Visitou o culto de jovens. Solicitou visita pastoral.</p>"}
    ]

    for m_data in membros_completos:
        m = Member(
            nome=m_data["nome"],
            sexo=m_data["sexo"],
            estado_civil=m_data["estado_civil"],
            conjuge=m_data["conjuge"],
            telefone=m_data["telefone"],
            email=m_data["email"],
            funcao=m_data["funcao"],
            dizimista=m_data["dizimista"],
            batizado=m_data["batizado"],
            data_nascimento=m_data["nasc"],
            data_batismo=m_data["batismo"],
            data_cadastro=m_data["cad"],
            data_saida=m_data["saida"],
            status=m_data["status"],
            cpf=m_data.get("cpf", ""),
            rg=m_data.get("rg", ""),
            endereco=m_data.get("endereco", "Rua das Acácias, 120"),
            bairro=m_data.get("bairro", "Jardim Esperança"),
            cep=m_data.get("cep", "01310-100"),
            observacoes=m_data.get("obs", ""),
            igreja_local="Sede Central",
            visitante=m_data["vis"]
        )
        db.session.add(m)
    
    db.session.commit()
    print(f"  ✅ {len(membros_completos)} membros, oficiais e visitantes cadastrados com histórico 2025/2026.")

def seed_ebd():
    print("📖 [3/6] Povoando Escola Bíblica Dominical (EBD)...")
    from scripts.seed_ebd import seed_ebd as run_ebd_seed
    run_ebd_seed()

def seed_patrimonio():
    print("🏛️ [4/6] Povoando Gestão de Patrimônio e Bens...")
    import importlib.util
    spec = importlib.util.spec_from_file_location("seed_pat", str(BASE_DIR / "scripts" / "seed_patrimonio.py"))
    pat_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pat_mod)

def seed_documentos_eventos():
    print("📅 [5/6] Povoando Calendário de Eventos, Atas, Cartas e Certificados...")
    import importlib.util
    spec = importlib.util.spec_from_file_location("seed_doc", str(BASE_DIR / "scripts" / "seed_documentos_eventos.py"))
    doc_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(doc_mod)

def seed_financeiro():
    print("💰 [6/6] Povoando Módulo Financeiro (Dízimos, Ofertas e Despesas)...")
    import importlib.util
    spec = importlib.util.spec_from_file_location("seed_fin", str(BASE_DIR / "scripts" / "seed_financeiro.py"))
    fin_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fin_mod)

def main():
    print("\n" + "=" * 70)
    print("  🌱 SIGI — POVOAMENTO COMPLETO DA BASE DE DADOS")
    print("=" * 70 + "\n")
    
    with app.app_context():
        db.create_all()
        seed_igreja()
        seed_membros()
        seed_ebd()
        seed_patrimonio()
        seed_documentos_eventos()
        seed_financeiro()

    print("\n" + "=" * 70)
    print("  🎉 BASE DE DADOS POVOADA COM 100% DE SUCESSO!")
    print("  Todos os módulos, gráficos e relatórios agora contêm dados realistas.")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    main()
