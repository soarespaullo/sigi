# 📊 ANÁLISE COMPLETA DO CÓDIGO-FONTE & PLANO DE BACKLOG KANBAN — SiGI
**Sistema Integrado de Gestão de Igreja (SiGI)**  
*Documento Técnico de Diagnóstico, Arquitetura, Mapeamento e Cartões de Execução para Trello*

---

## 1. 🔍 DIAGNÓSTICO TÉCNICO DO PROJETO

### 1.1. Visão Geral da Stack Tecnológica
* **Linguagem & Runtime:** Python 3.12+
* **Framework Web:** Flask 3.x (Padrão Application Factory e Blueprints modulares)
* **ORM & Banco de Dados:** SQLAlchemy / Flask-SQLAlchemy 3.1+, Flask-Migrate (Alembic), PyMySQL (MySQL/MariaDB) e SQLite 3
* **Autenticação & Segurança:** Flask-Login, Flask-WTF (CSRF Protection), Werkzeug Security, Bleach (Sanitização HTML), ItsDangerous
* **E-mail & Documentos:** Flask-Mail (SMTP), WeasyPrint (Engine PDF/HTML)
* **Frontend:** Bootstrap 5.3, Bootstrap Icons, Chart.js 3.9, Quill Editor 1.3.7, Vanilla CSS/JS com busca tolerante a acentuação e integração ViaCEP

---

### 1.2. O que já está implementado e funcional
1. **Autenticação e Primeiro Acesso:**
   * Configuração inicial (`/auth/setup`) para criação do primeiro administrador quando o banco está zerado.
   * Login (`/auth/login`) com hashing seguro e salted passwords (`generate_password_hash`/`check_password_hash`).
   * Recuperação de senha (`/auth/forgot_password` e `/auth/reset_password/<token>`) com expiração de 1 hora via `URLSafeTimedSerializer`.
   * Logout seguro e proteção de rotas com controle de sessão.
2. **Matriz de Permissões e Governança RBAC:**
   * Decorator de acesso `@permission_required(area, action)` protegendo endpoints no backend.
   * Helper global `has_permission(area, action)` injetado no contexto Jinja2 para renderização condicional da interface.
   * Matriz visual de permissões por usuário no painel de configurações.
3. **Escola Bíblica Dominical (EBD):**
   * Períodos letivos / trimestres com controle de status (`planejado`, `em_andamento`, `encerrado`).
   * Classes e turmas organizadas por faixa etária e sala.
   * Matrículas com status (`ativo`, `inativo`, `transferido`, `desligado`).
   * Registro de chamadas e frequência individualizada (`presente`, `falta`, `falta_justificada`, `visitante`).
   * Corpo docente e portal do professor "Minhas Classes".
4. **Secretaria & Membresia:**
   * Cadastro e edição completa de membros e visitantes (dados civis, eclesiásticos, endereço, filiação e foto).
   * Listagem paginada com filtros por status (`Ativo`, `Transferido`, `Inativo`).
   * Aniversariantes do mês com filtros por função e intervalo de dias.
   * Geração de link público com token criptográfico (`PublicLink`) para auto-cadastro de visitantes no hall da igreja sem necessidade de autenticação.
   * Vínculo direto de membro para usuário do sistema (1:1) com escolha de perfis predefinidos.
5. **Tesouraria & Finanças:**
   * Lançamento de receitas e despesas com categorias eclesiásticas padronizadas.
   * Segregação por contas bancárias e fundos eclesiásticos (Caixa Geral, Missões, Construção, Ação Social).
   * Balancete mensal oficial, controle de dizimistas e extrato individualizado por membro.
   * Upload e galeria de comprovantes de despesas.
6. **Patrimônio & Inventário:**
   * Cadastro de bens com número de tombamento, situação, valor contábil e data de aquisição.
   * Relatório de inventário consolidado com totalizadores por categoria de patrimônio.
7. **Documentos Eclesiásticos:**
   * Livro de Atas de reuniões com controle de situação (`Rascunho`, `Aprovada`, `Arquivada`).
   * Cartas pastorais de recomendação e transferência vinculadas a membros.
   * Emissão de certificados eclesiásticos com impressão formatada.
8. **APIs Centrais:**
   * API ViaCEP (`/api/cep/<cep>`) com tratamento defensivo e zero dependências externas.
   * API de Busca Global (`/api/busca/*`) com normalização diacrítica e suporte a nomes acentuados.

---

### 1.3. O que está parcialmente implementado
* **Geração de PDF (WeasyPrint):** A exportação de Carteirinhas, Fichas e Cartas em PDF depende de bibliotecas nativas de sistema (GTK+/Cairo/Pango). O tratamento de exceções está incompleto em algumas rotas de `member.py`, disparando erro 500 caso o host de produção não possua os pacotes compilados instalados.
* **Uploads Centralizados:** Foi criado o `UploadService`, porém `member.py` e `usuarios.py` ainda realizam salvamento manual de arquivos com regras dispersas e caminhos divergentes.
* **Dashboard Executivo:** O cálculo de tendências em `dashboard_service.py` puxa dados brutos para processar em memória via loops Python em vez de usar agregações nativas no banco SQL (`func.sum`, `func.count`).

---

### 1.4. O que está quebrado
* ❌ **Rotina de Backup com SQLite:** A rota `/configuracoes/backup/gerar` utiliza expressão regular que aceita apenas URIs no formato MySQL (`mysql+pymysql://...`). Em ambientes rodando SQLite, a execução falha imediatamente com a mensagem `"DATABASE_URL inválido ou não configurado."`.
* ❌ **Vazamento de Arquivos Temporários de Backup:** Ao gerar o arquivo `.zip` para download, o arquivo temporário criado no disco do servidor nunca é excluído após a entrega da resposta HTTP via `send_file`.
* ❌ **Exclusão de Membros com Histórico Financeiro (Foreign Key Crash):** O modelo `Financeiro` referencia `members.id` sem `ondelete="SET NULL"`. Se um membro que já dizimou for excluído, o banco recusa a operação e o sistema dispara erro 500 (`IntegrityError`).
* ❌ **Inconsistência de Caminho nos Avatares de Usuários:** `usuarios.py` armazena a foto como `user_1.png`, enquanto `member.py` armazena `uploads/foto.png`. No template `base.html`, a concatenação `'uploads/' ~ current_user.foto` duplica o prefixo (`uploads/uploads/...`) para membros vinculados, quebrando a exibição da foto.

---

### 1.5. Problemas de Segurança e Privacidade
* 🚨 **Vazamento de E-mails em Massa (Violação LGPD):** A função de envio de lembretes de eventos (`enviar_lembretes_eventos`) adiciona todos os membros da igreja no campo direto de destinatários (`To:`), expondo os endereços de e-mail de todos os membros publicamente para todos que recebem a mensagem.
* 🚨 **Exposição de Credenciais na Tabela de Processos do SO:** O backup executa `mysqldump` passando a senha em texto claro na linha de comando (`-p{password}`), o que permite a visualização da senha por qualquer usuário com acesso ao comando `ps aux` ou monitor do sistema.
* 🚨 **Envio Síncrono Bloqueante de Mensagens:** O envio de e-mails em massa ocorre dentro do ciclo da requisição HTTP normal. Isso pode travar as threads do servidor WSGI/Gunicorn e causar timeout (HTTP 504) em congregações com mais de 50 membros.

---

### 1.6. Problemas de Banco de Dados e Arquitetura
* **Falta de Versionamento Formal de Migrações:** Não existe o diretório `migrations/` no repositório. O schema vem sendo modificado com comandos manuais `ALTER TABLE` inseridos no `create_app()` de `app/__init__.py`.
* **Falta de Índices de Consulta:** Não há índices declarados nos campos mais filtrados do sistema (`Member.cpf`, `Member.status`, `Financeiro.data`, `Financeiro.tipo`, `EbdMatricula.classe_id`).
* **Imports Inconsistentes da Instância do DB:** Diversos arquivos importam `from app import db` em vez do singleton oficial `from app.extensions import db`, criando acoplamento e risco de importação circular.

---

## 2. 🏛️ MAPEAMENTO DOS MÓDULOS DO SIGI

| Módulo | Status no Código | Evidências no Código-Fonte |
| :--- | :---: | :--- |
| **🔐 Autenticação & Perfil** | **EXISTE** | `app/routes/auth/`, `app/routes/perfil/`, `User`, `Permission`, `UserPermission` |
| **📊 Dashboard Geral** | **EXISTE** | `app/routes/dashboard/`, `app/services/dashboard_service.py` |
| **👥 Secretaria, Membros & Visitantes** | **EXISTE** | `app/routes/member/`, `Member`, `PublicLink` |
| **🏫 Escola Bíblica Dominical (EBD)** | **EXISTE** | `app/routes/ebd/`, `EbdConfig`, `EbdPeriodo`, `EbdClasse`, `EbdMatricula`, etc. |
| **💰 Tesouraria & Finanças** | **EXISTE** | `app/routes/financeiro/`, `Financeiro`, Dízimos, Balancete Contábil |
| **📅 Eventos & Agenda Eclesiástica** | **EXISTE** | `app/routes/event/`, `Evento`, Links Públicos com Token |
| **📋 Documentos (Atas, Cartas, Certificados)** | **EXISTE** | `app/routes/documentos/` (`atas`, `cartas`, `certificados`) |
| **📦 Patrimônio & Inventário** | **EXISTE** | `app/routes/patrimonio/`, `Patrimonio` |
| **⚙️ Configurações & Governança** | **EXISTE** | `app/routes/configuracoes/` (Igreja, Usuários, Permissões, Backup, Logs, E-mail) |
| **🌐 APIs Internas & Autocomplete** | **EXISTE** | `app/routes/api/` (ViaCEP, busca tolerante a acentuação) |
| **🏛️ Departamentos / Ministérios** | **PARCIAL** | Não há tabela própria; existe apenas lista fixa de strings em `financeiro.py` |
| **🔄 Escalas de Voluntários & Cultos** | **NÃO EXISTE** | Sem modelos, controladores ou rotas |
| **🏠 Células / Grupos Pequenos** | **NÃO EXISTE** | Sem modelos, controladores ou rotas |
| **📱 Comunicação em Massa (WhatsApp/SMS)** | **NÃO EXISTE** | Apenas envio básico de e-mail SMTP |
| **📜 Auditoria Avançada (Change Diff Log)** | **NÃO EXISTE** | Tabela de log registra apenas texto simples da tarefa |

---

## 3. 🚨 TOP 5 PROBLEMAS MAIS CRÍTICOS

1. **Vazamento de Privacidade LGPD no Envio de E-mails:** Inserção de todos os destinatários no campo `To:` em `app/routes/event/event.py`.
2. **Crash 500 na Exclusão de Membros com Histórico Financeiro:** Falta de integridade referencial defensiva em `app/models/financeiro.py`.
3. **Backup Quebrado para SQLite e Acúmulo de Arquivos Temporários:** Falha de compatibilidade e falta de exclusão de arquivos em `app/routes/configuracoes/backup/backup.py`.
4. **Ausência de Migrações Versionadas via Alembic:** Manipulação manual e instável de colunas do banco no arquivo `app/__init__.py`.
5. **Inconsistência no Caminho das Imagens de Perfil:** Prefixos duplicados no Jinja2 que quebram avatares de usuários vinculados a membros.

---

## 4. 📋 AS 10 PRIMEIRAS TAREFAS PARA O TRELLO

1. `[P0]` **Correção de Privacidade LGPD no Envio de Lembretes de Eventos**
2. `[P0]` **Ajuste de Integridade Referencial na Exclusão de Membros (FK Financeiro)**
3. `[P0]` **Suporte a Backup SQLite e Limpeza de Arquivos Temporários**
4. `[P0]` **Inicialização Oficial de Migrações com Flask-Migrate (Alembic)**
5. `[P1]` **Unificação e Padronização de Armazenamento de Avatares via UploadService**
6. `[P1]` **Fallback Seguro para Geração de PDFs (WeasyPrint)**
7. `[P1]` **Padronização dos Imports da Instância do Banco (`app.extensions.db`)**
8. `[P1]` **Configuração de Estrutura Oficial de Testes Automatizados com Pytest**
9. `[P2]` **Otimização de Consultas Agregadas na Dashboard Service (SQL Nativo)**
10. `[P2]` **Criação da Entidade e Cadastro Dinâmico de Departamentos/Ministérios**

---

## 5. 🗂️ ESTRUTURA DO QUADRO KANBAN NO TRELLO

### 5.1. Estrutura de Listas (Colunas do Fluxo)

```
┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────────────┐
│ 📥 Backlog  ├──►│ 🔎 Análise  ├──►│  📝 A Fazer ├──►│ 🔨 Em Desenvolvimento│
└─────────────┘   └─────────────┘   └─────────────┘   └──────────┬──────────┘
                                                                 │
┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌──────────▼──────────┐
│ ✅ Concluído│◄──┤🟣Homologação│◄──┤  🧪 Testes  │◄──┤   👀 Code Review    │
└─────────────┘   └─────────────┘   └──────┬──────┘   └─────────────────────┘
                                           │
                                    ┌──────▼──────┐
                                    │   🐛 Bugs   │
                                    └─────────────┘
```

### 5.2. Regras de Transição de Colunas

| Lista | Quando a tarefa entra? | O que acontece nela? | Critério de saída |
| :--- | :--- | :--- | :--- |
| **📥 Backlog** | Descoberta ou solicitação de melhoria/correção. | Classificação por Épico, Prioridade e Módulo. | Seleção para planejamento do ciclo de desenvolvimento. |
| **🔎 Análise** | Tarefa escolhida para refinamento técnico. | Especificação detalhada, levantamento de arquivos e critérios de aceite. | Sem dúvidas técnicas ou dependências não resolvidas. |
| **📝 A Fazer** | Especificação pronta e aprovada. | Fila de espera aguardando desenvolvedor livre. | Desenvolvedor assume a tarefa e inicia a branch. |
| **🔨 Em Desenvolvimento** | Início da codificação pelo desenvolvedor. | Codificação, refatoração e testes locais. | Código pronto, funcional e testes locais executando 100%. |
| **👀 Code Review** | Pull Request aberto no repositório. | Revisão por pares de segurança, arquitetura e boas práticas. | PR aprovado sem pendências ou débitos adicionais. |
| **🧪 Testes** | Build em ambiente de testes/staging. | Execução de testes de regressão e validação dos critérios de aceite. | Todos os critérios de aceite validados com sucesso. |
| **🟣 Homologação** | Validação técnica concluída. | Validação funcional pelo usuário final/pastor/secretaria. | Aceite formal do usuário ou PO. |
| **✅ Concluído** | Aprovada na homologação. | Deploy em produção realizado com sucesso. | N/A (Estado final da tarefa). |
| **🐛 Bugs** | Falha identificada durante os testes ou homologação. | Diagnóstico da causa raiz e definição de prioridade. | Movida para `A Fazer` ou `Em Desenvolvimento`. |

---

### 5.3. Sistema de Etiquetas (Labels do Trello)

* **Prioridades:**
  * `🔴 P0 — Crítico` (Impede o uso, risco de segurança ou perda de dados)
  * `🟠 P1 — Alta` (Necessário para a versão funcional / MVP estável)
  * `🟡 P2 — Média` (Importante para a gestão, não bloqueia o uso principal)
  * `🟢 P3 — Baixa` (Melhoria de usabilidade, otimização ou recurso futuro)
* **Tipos de Tarefa:**
  * `🔵 Feature` | `🐛 Bug` | `🔐 Segurança` | `🗄️ Banco de Dados` | `🎨 UX/UI` | `🧪 Testes` | `🚀 DevOps` | `🔧 Refatoração` | `⚡ Performance`
* **Módulos do Sistema:**
  * `[Membro]` | `[Financeiro]` | `[EBD]` | `[Eventos]` | `[Documentos]` | `[Patrimônio]` | `[Configurações]` | `[Auth]` | `[Dashboard]` | `[Core]`

---

## 6. 🗺️ ROADMAP EM 6 FASES

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ FASE 1: FUNDAÇÃO (Segurança, Banco, Migrações, LGPD, Correções Críticas)    │
├─────────────────────────────────────────────────────────────────────────────┤
│ FASE 2: MVP & ESTABILIDADE (Secretaria, Finanças, EBD, Uploads, PDFs)       │
├─────────────────────────────────────────────────────────────────────────────┤
│ FASE 3: GESTÃO ECLESIÁSTICA (Departamentos Dinâmicos, Patrimônio, Atas)     │
├─────────────────────────────────────────────────────────────────────────────┤
│ FASE 4: INTELIGÊNCIA & RELATÓRIOS (Dashboards Otimizados, Métricas Anuais)  │
├─────────────────────────────────────────────────────────────────────────────┤
│ FASE 5: QUALIDADE & UX (Testes Automatizados, Design System, Responsividade)│
├─────────────────────────────────────────────────────────────────────────────┤
│ FASE 6: PRODUÇÃO & GOVERNANÇA (Deploy, Backup Automático, Monitoramento)    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 7. 📦 CARTÕES DE TAREFAS FORMATADOS PARA O TRELLO

---

### [P0] Correção de Privacidade LGPD no Envio de Lembretes de Eventos

**Descrição:**  
O disparo de e-mails em lote coloca todos os destinatários no campo `To:`, expondo a lista de e-mails de todos os membros entre si. É necessário alterar para envio individualizado ou uso de cópia oculta (`Bcc`), além de tratar o envio de forma segura.

**Módulo:**  
Eventos & Agenda

**Tipo:**  
Segurança

**Dependências:**  
Nenhuma

**Critérios de aceite:**
- Nenhum membro recebe o e-mail enxergando os endereços de outros membros.
- O disparo de e-mails trata erros de conexão individualmente sem abortar a lista inteira.
- Registro de log de auditoria com quantidade de e-mails disparados com sucesso.

**Arquivos:**  
- `app/routes/event/event.py`

**Épico:**  
🔐 Autenticação e Segurança

---

### [P0] Ajuste de Integridade Referencial na Exclusão de Membros

**Descrição:**  
Ao excluir um membro que possui registros de dízimo ou ofertas na tabela `financeiro`, a aplicação estoura erro 500 (`IntegrityError`). Deve-se implementar `ondelete="SET NULL"` na coluna `membro_id` do modelo `Financeiro` ou aplicar exclusão lógica / verificação prévia no controlador de membros.

**Módulo:**  
Membros / Financeiro

**Tipo:**  
Banco de Dados / Bug

**Dependências:**  
Nenhuma

**Critérios de aceite:**
- Excluir um membro com histórico de dízimo não quebra a aplicação.
- Os lançamentos financeiros permanecem íntegros, mantendo o histórico de valores e categorias.
- Mensagem informativa caso o membro possua lançamentos vinculados.

**Arquivos:**  
- `app/models/financeiro.py`
- `app/routes/member/member.py`

**Épico:**  
👥 Gestão de Membros

---

### [P0] Suporte a Backup SQLite e Limpeza de Arquivos Temporários

**Descrição:**  
A rota de geração de backup falha quando o sistema utiliza banco SQLite e não remove os arquivos `.zip` temporários após o envio ao usuário. Deve-se suportar cópia segura do arquivo SQLite e implementar limpeza automática do arquivo temporário via `after_this_request` ou `tempfile` com contexto seguro.

**Módulo:**  
Configurações

**Tipo:**  
Bug / DevOps

**Dependências:**  
Nenhuma

**Critérios de aceite:**
- O backup funciona perfeitamente tanto em SQLite (`.db`) quanto em MySQL (`mysqldump`).
- Nenhum arquivo temporário órfão permanece ocupando espaço no disco do servidor.
- Tratamento de exceção amigável caso o executável `mysqldump` não esteja no `PATH`.

**Arquivos:**  
- `app/routes/configuracoes/backup/backup.py`

**Épico:**  
⚙️ Configurações

---

### [P0] Inicialização Oficial de Migrações de Banco com Alembic

**Descrição:**  
Inicializar a árvore formal de migrações (`flask db init`) e substituir a auto-migração imperativa que existe dentro do `create_app()` por scripts versionados do Alembic.

**Módulo:**  
Core / Banco de Dados

**Tipo:**  
Banco de Dados / Refatoração

**Dependências:**  
Nenhuma

**Critérios de aceite:**
- Diretório `migrations/` criado e versionado no Git.
- Primeira migration inicial gerada a partir dos modelos atuais do SQLAlchemy.
- Remoção do bloco try/except com `ALTER TABLE` em runtime de `app/__init__.py`.

**Arquivos:**  
- `app/__init__.py`
- `migrations/`

**Épico:**  
🔧 Débito Técnico

---

### [P1] Padronização e Unificação de Uploads via UploadService

**Descrição:**  
Os módulos de membros e usuários realizam salvamento manual de arquivos com convenções divergentes de caminhos de avatar. Refatorar todos os controllers para utilizar exclusivamente a classe `UploadService` com validação de extensão, tamanho máximo e geração segura de nomes UUID.

**Módulo:**  
Membros / Usuários

**Tipo:**  
Refatoração / Segurança

**Dependências:**  
Nenhuma

**Critérios de aceite:**
- `member.py` e `usuarios.py` utilizam `UploadService.save_image()`.
- O template `base.html` renderiza avatares de usuários e membros sem gerar duplicação de `uploads/uploads/`.
- Arquivos de imagem antigos são removidos do disco ao serem substituídos ou excluídos.

**Arquivos:**  
- `app/services/upload_service.py`
- `app/routes/member/member.py`
- `app/routes/configuracoes/usuarios/usuarios.py`
- `app/templates/base.html`

**Épico:**  
🔧 Débito Técnico

---

### [P1] Tratamento Defensivo na Geração de Documentos em PDF

**Descrição:**  
As rotas de emissão de Carteira, Ficha de Membro e Carta de Recomendação invocam `WeasyPrint` diretamente sem verificar se o binário ou dependências nativas (GTK/Pango) estão instalados, causando erro 500 fatal caso haja falha de carregamento da DLL/shared object.

**Módulo:**  
Membros / Documentos

**Tipo:**  
Bug / UX

**Dependências:**  
Nenhuma

**Critérios de aceite:**
- Todas as rotas de PDF verificam a disponibilidade do `HTML` do WeasyPrint.
- Em caso de indisponibilidade, o usuário é redirecionado com flash message amigável orientando a impressão via navegador (HTML print CSS).

**Arquivos:**  
- `app/routes/member/member.py`
- `app/routes/financeiro/financeiro.py`

**Épico:**  
📋 Relatórios e Documentos

---

### [P1] Correção de Imports Circulares e Inconsistências do SQLAlchemy

**Descrição:**  
Padronizar a importação da extensão `db` em todos os controladores e modelos, eliminando importações diretas de `from app import db` e adotando estritamente `from app.extensions import db`.

**Módulo:**  
Documentos

**Tipo:**  
Refatoração

**Dependências:**  
Nenhuma

**Critérios de aceite:**
- Nenhuma rota ou model importa `db` diretamente de `app`.
- Todos os arquivos utilizam `from app.extensions import db`.
- Eliminação de alertas de importação circular no boot da aplicação.

**Arquivos:**  
- `app/routes/documentos/atas/atas.py`
- `app/routes/documentos/cartas/cartas.py`
- `app/routes/documentos/certificados/certificados.py`

**Épico:**  
🔧 Débito Técnico

---

### [P1] Criação de Suíte Estruturada de Testes Automatizados (Pytest)

**Descrição:**  
Criar um diretório oficial `tests/` com `conftest.py`, fixtures de banco de dados SQLite em memória e testes automatizados para fluxos de autenticação, permissões RBAC, lançamentos financeiros e rotas críticas da EBD.

**Módulo:**  
Testes

**Tipo:**  
Teste / DevOps

**Dependências:**  
Nenhuma

**Critérios de aceite:**
- Comando `pytest` executa todos os testes de forma independente sem alterar o banco de desenvolvimento.
- Cobertura de testes nos decorators de permissão e endpoints de autenticação.
- Script de execução local e integração rápida no terminal.

**Arquivos:**  
- `tests/conftest.py` (NOVO)
- `tests/test_auth.py` (NOVO)
- `tests/test_permissions.py` (NOVO)
- `tests/test_financeiro.py` (NOVO)

**Épico:**  
🧪 Testes e Qualidade

---

### [P2] Otimização de Performance no Dashboard Service

**Descrição:**  
Substituir a filtragem e iteração em listas Python de `Financeiro.query.all()` e `Member.query.all()` por agregações diretas via SQL com `func.sum()`, `func.count()` e cláusulas `group_by`.

**Módulo:**  
Dashboard

**Tipo:**  
Performance

**Dependências:**  
Nenhuma

**Critérios de aceite:**
- Redução de consumo de memória na renderização do dashboard principal.
- Consultas SQL agregadas retornando diretamente os totais por ano, mês e categoria.
- Tempo de resposta da rota `/dashboard` inferior a 200ms em bases com grande volume de dados.

**Arquivos:**  
- `app/services/dashboard_service.py`
- `app/routes/dashboard/dashboard.py`

**Épico:**  
📊 Dashboard

---

### [P2] Cadastro Dinâmico de Departamentos e Ministérios

**Descrição:**  
Atualmente os departamentos da igreja são uma lista estática de strings em `financeiro.py`. Criar um modelo `Departamento` com CRUD completo em Configurações para permitir personalização de acordo com cada congregação (Ex: Ministério de Louvor, Diaconia, EBD, Jovens).

**Módulo:**  
Configurações / Igreja

**Tipo:**  
Feature / Banco de Dados

**Dependências:**  
Inicialização das Migrações

**Critérios de aceite:**
- Tabela `departamentos` com nome, descrição, líder responsável (FK Member) e status ativo.
- Tela de gerenciamento em Configurações.
- Selects de lançamento financeiro e patrimônio populados dinamicamente a partir do banco.

**Arquivos:**  
- `app/models/departamento.py` (NOVO)
- `app/routes/configuracoes/igreja/`
- `app/routes/financeiro/forms.py`

**Épico:**  
⛪ Gestão da Igreja

---

### [P2] Criação de Índices de Busca no Banco de Dados

**Descrição:**  
Adicionar índices explícitos (`db.Index`) nas colunas com alto volume de filtros e joins: `Member.cpf`, `Member.status`, `Financeiro.data`, `Financeiro.tipo`, `Financeiro.categoria`, `EbdMatricula.classe_id`, `EbdFrequencia.aula_id`.

**Módulo:**  
Banco de Dados

**Tipo:**  
Performance / Banco de Dados

**Dependências:**  
Inicialização das Migrações

**Critérios de aceite:**
- Migration gerada com a criação de índices B-Tree para os campos mais consultados.
- Melhora no tempo de resposta das consultas de busca rápida e relatórios estatísticos.

**Arquivos:**  
- `app/models/member.py`
- `app/models/financeiro.py`
- `app/models/ebd.py`

**Épico:**  
🔧 Débito Técnico

---

### [P3] Implementação de Fila Assíncrona para Disparo de E-mails

**Descrição:**  
Envios de e-mails em lote travam a requisição HTTP. Implementar mecanismo de background task para envio assíncrono de notificações e lembretes de eventos.

**Módulo:**  
Core / Comunicação

**Tipo:**  
Performance / DevOps

**Dependências:**  
Nenhuma

**Critérios de aceite:**
- O clique em "Enviar Lembretes" responde imediatamente ao usuário com feedback visual.
- Os e-mails são processados em segundo plano com log de sucesso/falha gravado de forma assíncrona.

**Arquivos:**  
- `app/services/mail_service.py` (NOVO)
- `app/routes/event/event.py`

**Épico:**  
🚀 Deploy e Infraestrutura

---

### [P3] Registro de Auditoria com Histórico de Alterações (Diff Log)

**Descrição:**  
Evoluir a tabela simples `logs` para um sistema de auditoria detalhado, registrando não apenas a ação textual, mas o estado anterior e posterior dos registros editados (ex: alterações em dízimos e cadastros de membros).

**Módulo:**  
Configurações

**Tipo:**  
Feature / Segurança

**Dependências:**  
Nenhuma

**Critérios de aceite:**
- Gravação de snapshots JSON com valores alterados em operações de `UPDATE` e `DELETE`.
- Visualização do histórico de modificações no painel de Logs para usuários com permissão administrativa.

**Arquivos:**  
- `app/models/log.py`
- `app/routes/configuracoes/logs/logs.py`
- `app/templates/configuracoes/logs.html`

**Épico:**  
🔐 Autenticação e Segurança
