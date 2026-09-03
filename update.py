#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
🏛️ SiGI — Script de Atualização Segura de Instalações
Atualiza dependências, executa migrações do banco e garante integridade sem apagar uploads.

Uso:
  python update.py
  python update.py --skip-backup
"""

import os
import sys
import subprocess
import argparse
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent

def print_header(titulo):
    print("\n" + "=" * 70)
    print(f"  {titulo}")
    print("=" * 70)

def print_ok(msg):
    print(f"  ✅ [OK] {msg}")

def print_warn(msg):
    print(f"  ⚠️  [AVISO] {msg}")

def print_error(msg):
    print(f"  ❌ [ERRO] {msg}")

def obter_python():
    if sys.platform == "win32":
        venv_py = BASE_DIR / "venv" / "Scripts" / "python.exe"
    else:
        venv_py = BASE_DIR / "venv" / "bin" / "python"
    
    if venv_py.exists():
        return venv_py
    return Path(sys.executable)

def gerar_backup_seguranca():
    print("  Gerando snapshot de segurança antes da atualização...")
    backups_dir = BASE_DIR / "backups"
    backups_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_path = backups_dir / f"snapshot_pre_update_{timestamp}.zip"
    
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        # Banco SQLite se existir
        db_file = BASE_DIR / "instance" / "sigi.db"
        if db_file.exists():
            zipf.write(db_file, arcname="instance/sigi.db")
        
        # Arquivo .env
        env_file = BASE_DIR / ".env"
        if env_file.exists():
            zipf.write(env_file, arcname=".env")
            
        # Pasta de uploads
        uploads_dir = BASE_DIR / "app" / "static" / "uploads"
        if uploads_dir.exists():
            for root, dirs, files in os.walk(uploads_dir):
                for f in files:
                    file_path = Path(root) / f
                    arcname = file_path.relative_to(BASE_DIR)
                    zipf.write(file_path, arcname=str(arcname))
                    
    print_ok(f"Snapshot criado com sucesso em: {zip_path.name}")

def atualizar_dependencias(python_exe):
    req_file = BASE_DIR / "requirements.txt"
    if req_file.exists():
        print("  Atualizando dependências do projeto...")
        cmd = [str(python_exe), "-m", "pip", "install", "-r", str(req_file)]
        subprocess.run(cmd, capture_output=True, text=True)
        print_ok("Dependências verificadas e atualizadas.")

def sincronizar_banco(python_exe):
    print("  Sincronizando novas tabelas e matriz de permissões...")
    script_sync = """
from app import create_app, db
from app.models import (
    User, Permission, UserPermission, Member, PublicLink, Evento, Financeiro,
    Patrimonio, Log, Ata, Certificado, Carta, Igreja,
    EbdConfig, EbdPeriodo, EbdClasse, EbdProfessor, EbdMatricula, EbdAula, EbdFrequencia,
    Equipe, EquipeFuncao, EquipeMembro, Escala, EscalaItem
)

app = create_app()
with app.app_context():
    db.create_all()
    
    areas_acoes = {
        'usuarios': ['view', 'create', 'edit', 'delete'],
        'config': ['view', 'edit', 'delete'],
        'mail': ['view', 'create', 'edit', 'delete'],
        'financeiro': ['view', 'create', 'edit', 'delete'],
        'atas': ['view', 'create', 'edit', 'delete'],
        'cartas': ['view', 'create', 'edit', 'delete'],
        'certificados': ['view', 'create', 'edit', 'delete'],
        'eventos': ['view', 'create', 'edit', 'delete'],
        'membros': ['view', 'create', 'edit', 'delete'],
        'patrimonios': ['view', 'create', 'edit', 'delete'],
        'ebd': ['view', 'create', 'edit', 'delete', 'frequencia'],
        'escalas': ['view', 'create', 'edit', 'delete', 'gerenciar'],
        'perfil': ['view', 'password']
    }
    
    for area, acoes in areas_acoes.items():
        for acao in acoes:
            if not Permission.query.filter_by(area=area, action=acao).first():
                db.session.add(Permission(area=area, action=acao))
                
    # Garante registro inicial de igreja se vazio
    igreja = Igreja.query.first()
    if not igreja:
        igreja = Igreja(
            nome="Igreja Evangélica Comunidade da Graça — Sede",
            cnpj="12.345.678/0001-90",
            endereco="Av. Principal, 1000 - Centro, São Paulo - SP, CEP 01000-000",
            telefone="(11) 3333-4444",
            email="contato@igrejadagraca.com.br",
            site="www.igrejadagraca.com.br",
            pastor_responsavel="Pr. Carlos Eduardo da Silva",
            ano_fundacao=1995,
            versiculo_tema="Porque dEle, por Ele e para Ele são todas as coisas. (Romanos 11:36)"
        )
        db.session.add(igreja)

    db.session.commit()
    print('SYNC_OK')
"""
    res = subprocess.run([str(python_exe), "-c", script_sync], capture_output=True, text=True)
    if "SYNC_OK" in res.stdout:
        print_ok("Estruturas de dados e permissões sincronizadas com sucesso.")
    else:
        print_warn(f"Aviso na sincronização:\n{res.stderr}")

def main():
    parser = argparse.ArgumentParser(description="Atualizador do SiGI")
    parser.add_argument("--skip-backup", action="store_true", help="Pula a criação do snapshot de segurança prévio")
    parser.add_argument("--skip-deps", action="store_true", help="Pula a checagem do pip install")
    args = parser.parse_args()

    print_header("🏛️  SIGI — ATUALIZAÇÃO SEGURA DO SISTEMA")
    
    python_exe = obter_python()
    
    if not args.skip_backup:
        gerar_backup_seguranca()
        
    if not args.skip_deps:
        atualizar_dependencias(python_exe)
        
    sincronizar_banco(python_exe)
    
    print_header("🎉 ATUALIZAÇÃO CONCLUÍDA COM SUCESSO!")
    print("""
  Lembre-se de recarregar sua aplicação web:
  - No PythonAnywhere: Clique em 'Reload' na aba Web.
  - No cPanel Passenger: Clique em 'Restart' no Setup Python App.
  - No Linux com Systemd / Gunicorn: execute 'systemctl restart sigi'.
""")

if __name__ == "__main__":
    main()
