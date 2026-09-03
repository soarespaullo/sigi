# 📜 Changelog — SiGI (Sistema Integrado de Gestão de Igreja)

Todas as alterações notáveis deste projeto serão documentadas neste arquivo.
O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/) e este projeto adere ao [Semantic Versioning](https://semver.org/lang/pt-BR/).

---

## [V1.1.2] — 2026-09-03

### 🌙 Novas Funcionalidades
- **Dark Mode Completo (Modo Escuro):**
  - Design system profissional baseado em tokens semânticos na escala Slate (`#0b1120`, `#111827`, `#1e293b`, `#334155`), sem uso de preto puro (#000000) e com contraste ergonômico.
  - Prevenção síncrona de *Flash of Unstyled Theme* (Zero FOUC) diretamente no `<head>` do layout base.
  - Alternância instantânea de tema sem necessidade de recarregar a página e persistência automática no `localStorage`.
  - Seletor de tema posicionado exclusivamente em **Configurações ➔ Configurações Gerais ➔ Tema / Aparência** com botões `☀️ Claro` e `🌙 Escuro`.
  - Sincronização dinâmica em tempo real com gráficos Chart.js (eixos, legendas e gridlines), FullCalendar v6 e editor de texto rico Quill.

- **Numeração Automática de Carteirinha de Membros:**
  - Atribuição sequencial atômica sem duplicidades com formato de 5 dígitos iniciando em `00001` (ex: `00001`, `00002`, ..., `00060`).
  - Validade fixa de 365 dias calculada automaticamente na criação do membro.
  - Rota oficial `/membros/carteira/` equipada com seletor rápido no topo para emissão e impressão de credenciais de qualquer membro ativo.
  - Atualização retroativa executada com sucesso para os 59 membros existentes no banco.

- **Tombamento Automático de Patrimônio por Categoria:**
  - Padrão sequencial inteligente estabelecido: `PAT-IMO-###` (Imóveis), `PAT-VEI-###` (Veículos), `PAT-EQU-###` (Equipamentos) e `PAT-MOV-###` (Móveis).
  - Preenchimento em tempo real no formulário `/patrimonios/novo` com consulta assíncrona à API `/patrimonios/api/proxima-etiqueta`.
  - Blindagem no backend para geração automática da etiqueta caso o campo seja submetido em branco.

- **Visualização de Eventos com FullCalendar v6:**
  - Adicionada alternância fluida entre visualização em Lista e visualização em Calendário Mensal em `/eventos/`.
  - Modal dinâmico com detalhes do evento e ações de edição/exclusão.

- **Módulo de Escala de Obreiros & Voluntários:**
  - Gestão de escalas por equipes ministeriais, com visualização pública e exportação.

- **Identidade Visual e Navbar SaaS:**
  - Aplicação dos novos logotipos e favicon oficial do SiGI.
  - Navbar unificada e compacta, prevenindo quebras de layout em telas intermediárias e protegendo o perfil do usuário.

### 🐛 Correções & Melhorias
- **Blindagem de Documentos e Relatórios PDF:**
  - Resolução do `TypeError: 'NoneType' object is not callable` em `/membros/carta_recomendacao/` através do mecanismo à prova de falhas `gerar_ou_renderizar_pdf`, permitindo geração via WeasyPrint ou visualização/impressão direta via navegador (`window.print()`).
  - Resolução de `BuildError` (`member.index`) em `/membros/relatorio/pdf`.
  - Suporte a `/membros/carta_recomendacao/` sem parâmetro de ID na URL.
- **Correção da Seleção de Membros na Carteira:**
  - Correção da rota `/membros/carteira/` evitando erro 404 por concatenação indevida.

### 🧹 Limpeza & Otimização
- Remoção de 14 scripts temporários descartáveis de teste em `scripts/test_*.py`.
- Purga de 28 diretórios de cache `__pycache__` e arquivos `.pyc`.
- Exclusão de arquivos residuais e backups compactados obsoletos liberando espaço no repositório.

---

## [V1.0.2] — 2026-08-29
- Padronização estética dos cards de configurações e tela de configuração da Escola Dominical (EBD).
- Ajustes de permissões e controle de acesso por módulo.

---

## [V1.0.1] — 2026-08-28
- Instalação e deployment inicial automatizado para servidores Ubuntu/Apache.
- Módulos base de Secretaria, Financeiro, Patrimônio e Atas.
