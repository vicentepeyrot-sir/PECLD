# -*- coding: utf-8 -*-
"""
downloader.py
=============
Módulo responsável por toda a automação de download dos dados do portal GPM.

Funções disponíveis:
  - logarGpmChrome()         → Inicia o navegador e faz login no GPM
  - consulta_servico_abt()   → Baixa as notas em ABERTO (por contrato/planilha)
  - consulta_servico_exec()  → Baixa as notas EXECUTADAS/CONCLUÍDAS (dia atual)
  - status_download_file()   → Aguarda e confirma que o download foi concluído
  - unzip_files()            → Descompacta os arquivos .zip baixados
"""

import os
import time
import zipfile
import logging
from datetime import datetime

import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException

import config

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# LOGIN
# ---------------------------------------------------------------------------

def logarGpmChrome(hd=False):
    """
    Inicia o Chrome e faz login no portal GPM-BA.

    Parâmetros
    ----------
    hd : bool
        Se True, roda em modo headless (sem abrir janela do navegador).

    Retorna
    -------
    driver : WebDriver
        Instância do Selenium já autenticada.
    """
    chrome_options = Options()

    is_github_actions = os.getenv("GITHUB_ACTIONS") == "true"

    if is_github_actions:
        logger.info("Configurando Chrome para GitHub Actions (Headless)...")
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
    else:
        if hd:
            chrome_options.add_argument("--headless=new")

        # Tenta usar Chrome Portable se disponível
        portable_path = os.path.join(
            config.dir_path,
            "GoogleChromePortable64",
            "bin",
            "chromiumportable_painel.exe",
        )
        if os.path.exists(portable_path):
            logger.info(f"Usando Chrome Portable: {portable_path}")
            chrome_options.binary_location = portable_path
        else:
            logger.info("Chrome Portable não encontrado. Usando Chrome do sistema.")

    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--remote-debugging-port=0")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--log-level=3")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--silent")
    chrome_options.add_argument("--incognito")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-logging", "enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)

    try:
        caminho_chromedriver = os.path.join(config.dir_path, "chromedriver.exe")
        if os.path.exists(caminho_chromedriver):
            logger.info(f"Usando ChromeDriver local: {caminho_chromedriver}")
            service = Service(caminho_chromedriver)
            driver = webdriver.Chrome(service=service, options=chrome_options)
        else:
            logger.info("ChromeDriver local não encontrado. Usando Selenium Manager.")
            driver = webdriver.Chrome(options=chrome_options)

        # Força o download para o diretório TEMP mesmo em modo incógnito
        driver.execute_cdp_cmd("Page.setDownloadBehavior", {
            "behavior": "allow",
            "downloadPath": config.dir_temp
        })

        driver.set_page_load_timeout(300)
        driver.set_script_timeout(300)

    except Exception:
        logger.exception("Erro ao iniciar o Chrome. Verifique o chromedriver e o ambiente.")
        raise

    logger.info("Fazendo login no portal GPM-BA...")
    driver.get("https://sirtecba.gpm.srv.br/includes/common/logout.php")
    time.sleep(5)
    driver.get("https://sirtecba.gpm.srv.br/")

    wait = WebDriverWait(driver, 20)

    # Seletores do campo usuário (layout antigo e novo)
    SELETORES_LOGIN = [
        (By.ID, "idLogin"),
        (By.XPATH, "//input[@placeholder='Seu usuário']"),
        (By.XPATH, "//input[@type='text']"),
    ]
    # Seletores do campo senha
    SELETORES_SENHA = [
        (By.ID, "idSenha"),
        (By.XPATH, "//input[@placeholder='Sua senha']"),
        (By.XPATH, "//input[@type='password']"),
    ]
    # Seletores do botão Entrar
    SELETORES_ENTRAR = [
        (By.XPATH, "//input[contains(@value, 'ntrar')]"),
        (By.XPATH, "//button[contains(., 'Entrar')]"),
        (By.XPATH, "//*[@type='submit']"),
    ]

    def _encontrar(seletores, usar_wait=False):
        for by, valor in seletores:
            try:
                if usar_wait:
                    return wait.until(EC.presence_of_element_located((by, valor)))
                return driver.find_element(by, valor)
            except Exception:
                continue
        raise Exception(f"Nenhum seletor encontrou o elemento: {seletores}")

    # Verifica se já está logado
    try:
        driver.find_element(By.PARTIAL_LINK_TEXT, "Sair")
        logger.info("Login OK (sessão já estava ativa).")
    except Exception:
        try:
            campo_login = _encontrar(SELETORES_LOGIN, usar_wait=True)
            campo_login.send_keys(config.GPM_USER)

            campo_senha = _encontrar(SELETORES_SENHA)
            campo_senha.send_keys(config.GPM_PASSWORD)

            time.sleep(1)
            _encontrar(SELETORES_ENTRAR).click()
            time.sleep(5)
            logger.info("Login OK (nova sessão criada).")
        except Exception as e:
            screenshot_path = os.path.join(config.dir_temp, "login_erro.png")
            try:
                driver.save_screenshot(screenshot_path)
                logger.error(f"Screenshot salvo em: {screenshot_path}")
            except Exception:
                pass
            logger.error(
                f"Falha no login. URL atual: {driver.current_url} | "
                f"Título: {driver.title} | Erro: {e}"
            )
            raise RuntimeError(
                f"Não foi possível fazer login no GPM. "
                f"Verifique 'TEMP/login_erro.png'. Erro: {e}"
            ) from e

    return driver


# ---------------------------------------------------------------------------
# NOTAS EM ABERTO
# ---------------------------------------------------------------------------

def consulta_servico_abt(driver):
    """
    Baixa as notas de serviço com status ABERTO.

    A função lê a planilha 'parametro_stc.xlsx' (aba 'Contratos') e, para cada
    contrato listado, realiza uma consulta no GPM filtrando por status 'Aberto',
    baixa o relatório .zip e o renomeia com o padrão:
        cs_abertos_{ddmmyyyy}_g{N}.zip

    Parâmetros
    ----------
    driver : WebDriver
        Instância do Selenium já autenticada (retornada por logarGpmChrome).
    """
    logger.info("### Iniciando download de Notas em ABERTO ###")
    driver.switch_to.default_content()
    driver.get("https://sirtecba.gpm.srv.br//gpm/geral/consulta_servico.php")
    time.sleep(5)

    try:
        driver.switch_to.default_content()
        driver.switch_to.frame(1)
    except Exception:
        pass

    time.sleep(4)

    # Lê a planilha de contratos
    arquivo_excel = os.path.join(config.dir_path, "parametro_stc.xlsx")
    if not os.path.exists(arquivo_excel):
        logger.error(f"Planilha de parâmetros não encontrada: {arquivo_excel}")
        raise FileNotFoundError(f"Arquivo não encontrado: {arquivo_excel}")

    df_contratos = pd.read_excel(arquivo_excel, sheet_name="Contratos")
    logger.info(f"{len(df_contratos)} contrato(s) encontrado(s) na planilha.")

    for i, row in df_contratos.iterrows():
        contrato = row["Contratos"]
        if pd.isna(contrato):
            continue

        logger.info(f"Processando contrato {i + 1}/{len(df_contratos)}: {contrato}")

        # Preenche o campo Contrato
        driver.find_element(
            By.XPATH, "/html/body/form[4]/table/tbody/tr[12]/td[4]/div/div[1]"
        ).click()
        time.sleep(0.5)
        input_contrato = driver.find_element(
            By.XPATH, "/html/body/form[4]/table/tbody/tr[12]/td[4]/div/input"
        )
        input_contrato.send_keys(str(contrato))
        time.sleep(0.5)
        input_contrato.send_keys(Keys.RETURN)

        # Preenche o campo Status como "Aberto"
        driver.find_element(
            By.XPATH, "//html/body/form[4]/table/tbody/tr[11]/td[2]/div"
        ).click()
        time.sleep(0.5)
        input_status = driver.find_element(
            By.XPATH, "//html/body/form[4]/table/tbody/tr[11]/td[2]/div/input"
        )
        input_status.send_keys("Aberto")
        time.sleep(0.5)
        input_status.send_keys(Keys.RETURN)

        # Clica em Consultar
        driver.find_element(By.NAME, "submit").click()
        time.sleep(10)

        # Trata alerta (sem resultados) ou faz o download
        try:
            alerta = driver.switch_to.alert
            alerta.accept()
            logger.warning(f"Contrato {contrato}: sem resultados (alerta dispensado).")
        except Exception:
            try:
                driver.switch_to.default_content()
                driver.switch_to.frame(1)
            except Exception:
                pass

            time.sleep(5)

            # Clica no botão de exportar
            driver.find_element(By.XPATH, '//*[@id="form"]/div[2]/a/button').click()
            time.sleep(3)

            window_handles = driver.window_handles
            if len(window_handles) > 1:
                driver.switch_to.window(window_handles[1])

            # Aguarda o download terminar
            status = status_download_file(config.dir_temp, "consulta_servicos_")

            if status[0] == 1:
                time.sleep(3)
                if len(window_handles) > 1:
                    driver.close()
                time.sleep(3)

            logger.info(f"Download concluído: contrato {contrato} (grupo {i + 1}).")

            # Renomeia o arquivo baixado
            try:
                atual_arq = os.path.join(config.dir_temp, status[1])
                periodo = datetime.now().strftime("%d%m%Y")
                novo_nome = f"cs_abertos_{periodo}_g{i + 1}.zip"
                novo_arq = os.path.join(config.dir_temp, novo_nome)
                os.rename(atual_arq, novo_arq)
                logger.info(f"Arquivo renomeado para: {novo_nome}")
            except Exception as e:
                logger.error(f"Erro ao renomear arquivo de abertos (grupo {i + 1}): {e}")

            # Volta para a janela principal
            time.sleep(2)
            driver.switch_to.window(window_handles[0])
            time.sleep(2)

            try:
                driver.switch_to.frame(1)
            except Exception:
                pass

            # Clica em Voltar para o próximo ciclo
            driver.find_element(
                By.XPATH, "//html/body/form[4]/div[3]/input"
            ).click()

    logger.info("### Download de Notas em ABERTO finalizado ###")


# ---------------------------------------------------------------------------
# NOTAS EXECUTADAS / CONCLUÍDAS
# ---------------------------------------------------------------------------

def consulta_servico_exec(driver, data_inicio=None, data_fim=None):
    """
    Baixa as notas de serviço EXECUTADAS/CONCLUÍDAS do período informado.

    Acessa a consulta de serviços do GPM, filtra pelo intervalo de datas (00:00 a 23:59),
    baixa o relatório .zip e o renomeia com o padrão:
        cs_executados_{ddmmyyyy}.zip  (ou cs_executados_{ini}_{fim}.zip para intervalos)

    Parâmetros
    ----------
    driver : WebDriver
        Instância do Selenium já autenticada (retornada por logarGpmChrome).
    data_inicio : date, optional
        Data inicial do período. Se None, usa hoje.
    data_fim : date, optional
        Data final do período. Se None, usa hoje.
    """
    logger.info("### Iniciando download de Notas EXECUTADAS ###")

    driver.get("https://sirtecba.gpm.srv.br//gpm/geral/consulta_servico.php")
    time.sleep(3)

    hoje = datetime.now().date()
    d_ini = data_inicio or hoje
    d_fim = data_fim or hoje

    data_ini = d_ini.strftime("%d/%m/%Y") + " 00:00"
    data_fim_str = d_fim.strftime("%d/%m/%Y") + " 23:59"

    try:
        driver.switch_to.frame(1)
    except Exception:
        pass

    time.sleep(3)

    # Preenche data inicial
    driver.find_element(
        By.XPATH, "//html/body/form[4]/table/tbody/tr[1]/td[2]/input[1]"
    ).clear()
    driver.find_element(
        By.XPATH, "//html/body/form[4]/table/tbody/tr[1]/td[2]/input[1]"
    ).send_keys(data_ini)
    time.sleep(2)

    # Preenche data final
    driver.find_element(
        By.XPATH, "//html/body/form[4]/table/tbody/tr[1]/td[2]/input[2]"
    ).clear()
    driver.find_element(
        By.XPATH, "//html/body/form[4]/table/tbody/tr[1]/td[2]/input[2]"
    ).send_keys(data_fim_str)
    time.sleep(3)

    # Clica em Consultar
    driver.find_element(By.NAME, "submit").click()
    time.sleep(10)

    # Trata alerta ou faz o download
    try:
        alerta = driver.switch_to.alert
        time.sleep(2)
        alerta.accept()
        logger.warning("Sem resultados de serviços executados (alerta dispensado).")
        time.sleep(8)
    except Exception:
        pass

    # Aguarda explicitamente o alerta (sem resultados) OU o botão CSV aparecer.
    # Em headless o alert pode demorar mais que no modo normal.
    try:
        WebDriverWait(driver, 20).until(EC.alert_is_present())
        driver.switch_to.alert.accept()
        logger.warning("Sem resultados de serviços executados para o período informado.")
        time.sleep(3)
        # Volta ao frame para poder clicar em "Voltar"
        try:
            driver.switch_to.default_content()
            driver.switch_to.frame(1)
        except Exception:
            pass
        try:
            driver.find_element(By.XPATH, "//html/body/form[4]/div[3]/input").click()
        except Exception:
            pass
        logger.info("### Download de Notas EXECUTADAS finalizado (sem resultados) ###")
        return
    except TimeoutException:
        pass  # Sem alerta = há resultados, continua

    time.sleep(5)

    # Re-estabelece o frame onde os resultados são exibidos.
    # Tenta frame(1); se não existir, permanece no contexto atual.
    for tentativa in range(3):
        try:
            driver.switch_to.default_content()
            driver.switch_to.frame(1)
            break
        except Exception:
            time.sleep(2)

    time.sleep(3)

    # Screenshot + HTML para diagnóstico (disponível como artefato se falhar)
    try:
        driver.save_screenshot(os.path.join(config.dir_temp, "pagina_resultado.png"))
    except Exception:
        pass

    # Tenta localizar o botão de exportar com múltiplos seletores.
    # Inclui fallback no default_content caso o botão esteja fora do iframe.
    CSV_SELECTORS = [
        (By.XPATH, "//*[contains(text(), 'CSV/Excel')]"),
        (By.XPATH, "//*[contains(translate(text(),'csvexel','CSVEXEL'), 'CSV')]"),
        (By.XPATH, "//a[contains(@href, 'csv')]"),
        (By.XPATH, "//button[contains(@onclick, 'csv')]"),
        (By.XPATH, "//input[contains(@value, 'CSV')]"),
        (By.XPATH, '//*[@id="form"]/div[2]/a/button'),
    ]

    btn_csv = None
    for contexto in ("frame", "default"):
        if contexto == "default":
            try:
                driver.switch_to.default_content()
            except Exception:
                pass
        for by, selector in CSV_SELECTORS:
            try:
                btn_csv = WebDriverWait(driver, 8).until(
                    EC.element_to_be_clickable((by, selector))
                )
                logger.info(f"Botão CSV encontrado ({contexto}): {selector}")
                break
            except (TimeoutException, Exception):
                continue
        if btn_csv:
            break

    if btn_csv is None:
        try:
            with open(os.path.join(config.dir_temp, "pagina_resultado.html"), "w", encoding="utf-8") as f:
                f.write(driver.page_source)
        except Exception:
            pass
        raise RuntimeError(
            "Botão CSV/Excel não encontrado. "
            "Verifique TEMP/pagina_resultado.png no artefato de diagnóstico."
        )

    btn_csv.click()
    time.sleep(5)

    window_handles = driver.window_handles
    if len(window_handles) > 1:
        driver.switch_to.window(window_handles[1])

    # Aguarda o download
    status = status_download_file(config.dir_temp, "consulta_servicos_")

    if status[0] == 1:
        time.sleep(2)
        if len(window_handles) > 1:
            driver.close()
        time.sleep(2)

    logger.info("Download de serviços executados concluído.")
    time.sleep(5)

    # Renomeia o arquivo
    try:
        atual_arq = os.path.join(config.dir_temp, status[1])
        if d_ini == d_fim:
            periodo = d_ini.strftime("%d%m%Y")
        else:
            periodo = f"{d_ini.strftime('%d%m%Y')}_{d_fim.strftime('%d%m%Y')}"
        novo_nome = f"cs_executados_{periodo}.zip"
        novo_arq = os.path.join(config.dir_temp, novo_nome)
        os.rename(atual_arq, novo_arq)
        logger.info(f"Arquivo renomeado para: {novo_nome}")
    except Exception as e:
        logger.error(f"Erro ao renomear arquivo de executados: {e}")

    time.sleep(3)
    driver.switch_to.window(window_handles[0])
    time.sleep(3)

    try:
        driver.switch_to.frame(1)
    except Exception:
        pass

    time.sleep(5)
    driver.find_element(By.XPATH, "//html/body/form[4]/div[3]/input").click()

    logger.info("### Download de Notas EXECUTADAS finalizado ###")


# ---------------------------------------------------------------------------
# UTILITÁRIOS
# ---------------------------------------------------------------------------

def status_download_file(path, nome):
    """
    Aguarda indefinidamente até que um arquivo com o prefixo 'nome' apareça
    no diretório 'path' e não esteja mais como .crdownload (em andamento).

    Retorna
    -------
    tuple : (1, nome_do_arquivo)
    """
    while True:
        resultado = [
            arq for arq in os.listdir(path)
            if nome in arq and ".crdownload" not in arq
        ]
        if resultado:
            return 1, resultado[0]
        time.sleep(1)


def unzip_files(caminho, prefixo="cs_", novo_nome=None):
    """
    Descompacta todos os arquivos .zip que começam com 'prefixo' no diretório 'caminho'.

    Parâmetros
    ----------
    caminho   : str  → Diretório onde estão os arquivos .zip
    prefixo   : str  → Prefixo dos arquivos a descompactar (padrão: 'cs_')
    novo_nome : str  → Se informado, renomeia o CSV extraído para esse nome
    """
    logger.info(f"Descompactando arquivos com prefixo '{prefixo}'...")
    for arquivo in os.listdir(caminho):
        if arquivo.startswith(prefixo) and arquivo.endswith(".zip"):
            filepath = os.path.join(caminho, arquivo)
            with zipfile.ZipFile(filepath, "r") as zf:
                for nome_interno in zf.namelist():
                    zf.extract(nome_interno, caminho)
                    extraido = os.path.join(caminho, nome_interno)
                    if novo_nome:
                        destino_nome = novo_nome + ".csv"
                    else:
                        destino_nome = arquivo.replace(".zip", ".csv")
                    destino = os.path.join(caminho, destino_nome)
                    if os.path.exists(destino):
                        os.remove(destino)
                    os.rename(extraido, destino)
    logger.info("Descompactação concluída.")
