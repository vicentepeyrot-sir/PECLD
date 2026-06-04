# -*- coding: utf-8 -*-
import os
from datetime import datetime, timezone, timedelta

# --- CONFIGURAÇÃO DE DIRETÓRIOS ---
# Caminho base do projeto
dir_path = os.path.dirname(os.path.realpath(__file__))

# Diretório onde os arquivos baixados ficam temporariamente
dir_temp = os.path.join(dir_path, 'TEMP')

# Diretório de cache do navegador
dir_cache = os.path.join(dir_path, 'cache')

# Lista de diretórios necessários
ALL_DIRS = [dir_temp, dir_cache]


def criar_diretorios():
    """Verifica se os diretórios necessários existem e os cria caso contrário."""
    for path in ALL_DIRS:
        if not os.path.exists(path):
            os.makedirs(path)
            print(f"Diretório criado: {path}")


def get_br_time():
    """Retorna a data e hora atual no fuso horário de Brasília (UTC-3)."""
    utc_now = datetime.now(timezone.utc)
    br_timezone = timezone(timedelta(hours=-3))
    return utc_now.astimezone(br_timezone)


# --- CREDENCIAIS GPM ---
# Configure as variáveis de ambiente GPM_USER e GPM_PASSWORD,
# ou crie os Secrets correspondentes no repositório GitHub.
# Localmente você pode criar um arquivo .env e carregá-lo antes de rodar.
GPM_USER = os.environ.get("GPM_USER", "")
GPM_PASSWORD = os.environ.get("GPM_PASSWORD", "")

# --- INICIALIZAÇÃO ---
# Garante que os diretórios existam ao importar este módulo
criar_diretorios()
