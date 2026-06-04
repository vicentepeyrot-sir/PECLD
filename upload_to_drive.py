# -*- coding: utf-8 -*-
"""
upload_to_drive.py
==================
Faz upload de data/dados_pecld.xlsx para a pasta do Google Drive compartilhado.

Autenticação:
  - Em produção (GitHub Actions): variável de ambiente GOOGLE_CREDENTIALS
    contendo o JSON da Service Account como string.
  - Localmente: lê o arquivo chaveGoogle.json na raiz do projeto.
"""
import os
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

FOLDER_ID  = "1_gHFgesfwyRKT3_7IqJyCTs4wY56bGar"
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
XLSX_LOCAL = os.path.join(BASE_DIR, "data", "dados_pecld.xlsx")
SCOPES     = ["https://www.googleapis.com/auth/drive"]


def _get_service():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    creds_json = os.environ.get("GOOGLE_CREDENTIALS")
    if creds_json:
        creds_dict = json.loads(creds_json)
    else:
        cred_file = os.path.join(BASE_DIR, "chaveGoogle.json")
        with open(cred_file, encoding="utf-8") as f:
            creds_dict = json.load(f)

    creds = service_account.Credentials.from_service_account_info(
        creds_dict, scopes=SCOPES
    )
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def upload():
    if not os.path.exists(XLSX_LOCAL):
        logger.warning(f"Arquivo não encontrado, upload ignorado: {XLSX_LOCAL}")
        return

    service = _get_service()
    nome = f"PECLD_{datetime.now().strftime('%Y-%m-%d')}.xlsx"
    mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    from googleapiclient.http import MediaFileUpload

    media = MediaFileUpload(XLSX_LOCAL, mimetype=mime, resumable=True)

    # Verifica se já existe arquivo com esse nome na pasta (evita duplicatas)
    query = f"name='{nome}' and '{FOLDER_ID}' in parents and trashed=false"
    result = service.files().list(
        q=query,
        fields="files(id,name)",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
    ).execute()
    existentes = result.get("files", [])

    if existentes:
        file_id = existentes[0]["id"]
        service.files().update(
            fileId=file_id,
            media_body=media,
            supportsAllDrives=True,
        ).execute()
        logger.info(f"Arquivo atualizado no Drive: {nome} (id: {file_id})")
    else:
        metadata = {"name": nome, "parents": [FOLDER_ID]}
        f = service.files().create(
            body=metadata,
            media_body=media,
            fields="id,name",
            supportsAllDrives=True,
        ).execute()
        logger.info(f"Arquivo criado no Drive: {f['name']} (id: {f['id']})")

    logger.info("Upload para o Google Drive concluído.")


if __name__ == "__main__":
    from logger_config import setup_logger
    setup_logger()
    upload()
