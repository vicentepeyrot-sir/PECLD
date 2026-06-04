# -*- coding: utf-8 -*-
"""
main.py — Vicente_WFM
=====================
Ponto de entrada do robô de download do GPM.

Executa em sequência:
  1. Login no portal GPM-BA
  2. Download das notas EXECUTADAS/CONCLUÍDAS → cs_executados_{data}.zip
  3. Descompactação dos arquivos baixados

Execute com:
    python main.py
"""

import os
import logging

import config
from logger_config import setup_logger
from downloader import (
    logarGpmChrome,
    consulta_servico_exec,
    unzip_files,
)
from sheets_uploader import enviar_para_sheets


def executar_downloads(data_inicio=None, data_fim=None):
    """
    Orquestra o login, download das notas e descompactação dos arquivos.
    Os arquivos CSV extraídos ficam disponíveis na pasta TEMP/.
    """
    setup_logger()
    logger = logging.getLogger(__name__)

    logger.info("=" * 60)
    logger.info("   INICIANDO VICENTE_WFM — Download de Notas GPM")
    logger.info("=" * 60)

    # ---------------------------------------------------------------
    # 1. Limpa arquivos temporários da execução anterior
    # ---------------------------------------------------------------
    logger.info("Limpando arquivos temporários anteriores...")
    for arquivo in os.listdir(config.dir_temp):
        caminho_arquivo = os.path.join(config.dir_temp, arquivo)
        try:
            os.remove(caminho_arquivo)
        except Exception as e:
            logger.warning(f"Não foi possível remover {arquivo}: {e}")

    # ---------------------------------------------------------------
    # 2. Faz login no portal GPM
    # ---------------------------------------------------------------
    logger.info("Iniciando o navegador e fazendo login no GPM...")
    driver = None
    try:
        driver = logarGpmChrome(hd=False)   # hd=True para rodar sem janela (headless)

        # -----------------------------------------------------------
        # 3. Download das notas EXECUTADAS / CONCLUÍDAS
        # -----------------------------------------------------------
        logger.info("--- Download: Notas EXECUTADAS ---")
        consulta_servico_exec(driver, data_inicio=data_inicio, data_fim=data_fim)

    except Exception:
        logger.exception("Erro durante o processo de download.")
        raise

    finally:
        if driver is not None:
            logger.info("Encerrando o navegador...")
            driver.quit()

    # ---------------------------------------------------------------
    # 5. Descompacta os .zip baixados → gera .csv na pasta TEMP/
    # ---------------------------------------------------------------
    logger.info("Descompactando arquivos baixados...")
    unzip_files(config.dir_temp, prefixo="cs_")

    # ---------------------------------------------------------------
    # 6. Lista os arquivos gerados para confirmação
    # ---------------------------------------------------------------
    arquivos_gerados = [
        f for f in os.listdir(config.dir_temp)
        if f.endswith(".csv") or f.endswith(".zip")
    ]
    logger.info("Arquivos disponíveis na pasta TEMP/:")
    for arq in sorted(arquivos_gerados):
        logger.info(f"  → {arq}")

    # ---------------------------------------------------------------
    # 7. Salva os dados processados na pasta do Drive
    # ---------------------------------------------------------------
    logger.info("Salvando os dados na pasta do Drive...")
    enviar_para_sheets(data_inicio=data_inicio, data_fim=data_fim)

    logger.info("=" * 60)
    logger.info("   PROCESSO CONCLUÍDO COM SUCESSO")
    logger.info("=" * 60)


if __name__ == "__main__":
    import argparse
    from datetime import date

    parser = argparse.ArgumentParser(description="Download de Notas GPM — PECLD")
    parser.add_argument("--desde", type=str, default=None,
                        help="Data de início no formato YYYY-MM-DD (padrão: hoje)")
    parser.add_argument("--ate", type=str, default=None,
                        help="Data de fim no formato YYYY-MM-DD (padrão: hoje)")
    args = parser.parse_args()

    data_inicio = date.fromisoformat(args.desde) if args.desde else None
    data_fim = date.fromisoformat(args.ate) if args.ate else None

    executar_downloads(data_inicio, data_fim)
