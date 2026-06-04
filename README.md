# PECLD — Painel de Análise

Painel interativo de notas de serviço do portal GPM-BA, com automação completa via GitHub Actions e publicação no GitHub Pages.

---

## Acesso ao painel

**URL pública:** https://vicentepeyrot-sir.github.io/PECLD/

**Localmente (Flask):** execute `iniciar.bat` e acesse http://localhost:5000

---

## Como os dados são atualizados

O GitHub Actions roda **todos os dias às 22:00 (horário de Brasília)** e executa automaticamente:

1. Faz login no portal GPM-BA via Chrome headless (Selenium)
2. Baixa as notas executadas do período
3. Processa e mescla com os dados acumulados em `data/dados_pecld.xlsx`
4. Gera os arquivos JSON estáticos em `data/`
5. Faz commit e push — o GitHub Pages atualiza automaticamente

### Disparo manual

Para forçar uma atualização fora do horário agendado:

1. Acesse: https://github.com/vicentepeyrot-sir/PECLD/actions
2. Clique em **"Atualizar Dados PECLD"**
3. Clique em **"Run workflow"**
4. Opcional: informe o período (ex: `2026-01-01` até `2026-06-04`)

No painel publicado, o botão **⬇ Atualizar Dados** abre diretamente essa página.

---

## Estrutura do projeto

```
site_pecld/
├── index.html              # Painel (funciona local com Flask e no GitHub Pages)
├── server.py               # Servidor Flask para uso local
├── main.py                 # Orquestra o download do GPM
├── downloader.py           # Automação Selenium (login + download)
├── sheets_uploader.py      # Processa CSVs e salva XLSX
├── generate_static.py      # Gera JSON estáticos para o GitHub Pages
├── escolher_datas.py       # Interface gráfica para escolha de datas (uso local)
├── config.py               # Configurações e credenciais via variáveis de ambiente
├── logger_config.py        # Configuração de logs
├── iniciar.bat             # Atalho para rodar o servidor local
├── requirements.txt        # Dependências Python
├── metas.json              # Metas por UTD (editável pelo painel local)
├── superintendencias.json  # Mapeamento UTD → Superintendência
├── parametro_stc.xlsx      # Planilha de contratos
├── data/
│   ├── dados_pecld.xlsx    # Banco de dados acumulado (atualizado pelo workflow)
│   ├── os.json             # Notas de serviço (gerado por generate_static.py)
│   ├── calendar.json       # Contagem por data
│   ├── files.json          # Lista de arquivos
│   ├── metas.json          # Metas (cópia para o GitHub Pages)
│   └── superintendencias.json
└── .github/
    └── workflows/
        └── daily.yml       # Workflow de automação diária
```

---

## Configuração no GitHub

### Secrets do repositório

Configurados em **Settings → Secrets and variables → Actions**:

| Secret | Valor |
|--------|-------|
| `GPM_USER` | Usuário do portal GPM-BA |
| `GPM_PASSWORD` | Senha do portal GPM-BA |

### GitHub Pages

Configurado em **Settings → Pages**:
- Source: **Deploy from a branch**
- Branch: **main** → Pasta: **/ (root)**

---

## Como rodar localmente

### Pré-requisitos

- Python 3.11+
- Google Chrome instalado

### Instalação

```bash
pip install -r requirements.txt
```

### Iniciar o servidor

Clique duas vezes em `iniciar.bat`, ou no terminal:

```bash
python server.py
```

Acesse: http://localhost:5000

### Baixar dados manualmente

```bash
# Baixar dados de hoje
python main.py

# Baixar período específico
python main.py --desde 2026-01-01 --ate 2026-06-04

# Gerar JSON estáticos a partir dos XLSX em data/
python generate_static.py
```

---

## Diferenças entre modo local e GitHub Pages

| Funcionalidade | Local (Flask) | GitHub Pages |
|---|---|---|
| Visualização de dados | ✅ | ✅ |
| Filtros e gráficos | ✅ | ✅ |
| Salvar metas | ✅ persiste no arquivo | ⚠️ só em memória |
| Salvar superintendências | ✅ persiste no arquivo | ⚠️ só em memória |
| Botão Atualizar Dados | ✅ abre janela local | ↗️ abre GitHub Actions |
| Dados sempre atualizados | Manual (bat) | Automático (22h diário) |

---

## Arquivos ignorados pelo Git

Os seguintes arquivos **não são enviados ao GitHub** (via `.gitignore`):

- `chaveGoogle.json` — credenciais Google (sensível)
- `TEMP/` — arquivos temporários de download
- `cache/` — cache do navegador
- `app.log`, `server_out.txt`, `server_err.txt` — logs de execução
- `__pycache__/`, `*.pyc` — cache Python

---

## Repositório

https://github.com/vicentepeyrot-sir/PECLD
