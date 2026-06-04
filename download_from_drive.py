# -*- coding: utf-8 -*-
"""
download_from_drive.py
======================
Baixa todos os arquivos PECLD*.xlsx da pasta do Google Drive para data/

Autenticação:
  - GitHub Actions: variável de ambiente GOOGLE_CREDENTIALS (JSON da Service Account)
  - Local: lê chaveGoogle.json na raiz do projeto
"""
import os
import json
import logging

logger = logging.getLogger(__name__)

FOLDER_ID = "1_gHFgesfwyRKT3_7IqJyCTs4wY56bGar"
BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
DATA_DIR  = os.path.join(BASE_DIR, "data")
SCOPES    = ["https://www.googleapis.com/auth/drive.readonly"]


def _get_service():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    creds_json = os.environ.get("GOOGLE_CREDENTIALS")
    if creds_json:
        creds_dict = json.loads(creds_json)
    else:
        with open(os.path.join(BASE_DIR, "chaveGoogle.json"), encoding="utf-8") as f:
            creds_dict = json.load(f)

    creds = service_account.Credentials.from_service_account_info(
        creds_dict, scopes=SCOPES
    )
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def download():
    os.makedirs(DATA_DIR, exist_ok=True)
    service = _get_service()

    # Lista todos os XLSX na pasta (inclusive Shared Drives)
    query = f"'{FOLDER_ID}' in parents and name contains 'PECLD' and trashed=false"
    result = service.files().list(
        q=query,
        fields="files(id, name, modifiedTime)",
        orderBy="modifiedTime desc",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
    ).execute()

    arquivos = [f for f in result.get("files", []) if f["name"].lower().endswith(".xlsx")]

    if not arquivos:
        logger.warning("Nenhum arquivo PECLD*.xlsx encontrado na pasta do Drive.")
        return 0

    logger.info(f"{len(arquivos)} arquivo(s) encontrado(s) na pasta do Drive.")

    from googleapiclient.http import MediaIoBaseDownload
    import io

    baixados = 0
    for arq in arquivos:
        destino = os.path.join(DATA_DIR, arq["name"])
        try:
            request  = service.files().get_media(
                fileId=arq["id"], supportsAllDrives=True
            )
            buffer   = io.BytesIO()
            downloader = MediaIoBaseDownload(buffer, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
            with open(destino, "wb") as f:
                f.write(buffer.getvalue())
            logger.info(f"  Baixado: {arq['name']}")
            baixados += 1
        except Exception as exc:
            logger.error(f"  Erro ao baixar {arq['name']}: {exc}")

    logger.info(f"Download concluído: {baixados}/{len(arquivos)} arquivo(s).")
    return baixados


if __name__ == "__main__":
    from logger_config import setup_logger
    setup_logger()
    download()
